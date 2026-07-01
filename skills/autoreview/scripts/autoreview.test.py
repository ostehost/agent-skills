#!/usr/bin/env python3
"""Hermetic unit tests for autoreview's pure/near-pure functions.

Unlike test-review-harness.py (a live-engine smoke/acceptance test requiring
installed, authenticated CLIs), this file imports autoreview directly and
exercises its logic with synthetic inputs -- no subprocess, no network, no
engine CLI required. Run: python3 skills/autoreview/scripts/autoreview.test.py
"""
from __future__ import annotations

import importlib.util
import os
import stat
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock


def _load_autoreview():
    autoreview_path = Path(__file__).resolve().parent / "autoreview"
    loader = SourceFileLoader("autoreview", str(autoreview_path))
    spec = importlib.util.spec_from_loader("autoreview", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


ar = _load_autoreview()


def make_report(**overrides):
    report = {
        "findings": [],
        "overall_correctness": "patch is correct",
        "overall_explanation": "looks fine",
        "overall_confidence": 0.9,
    }
    report.update(overrides)
    return report


def make_finding(**overrides):
    finding = {
        "title": "Example finding",
        "body": "Something is wrong here.",
        "priority": "P1",
        "confidence": 0.8,
        "category": "bug",
        "code_location": {"file_path": "src/app.py", "line": 10},
    }
    finding.update(overrides)
    return finding


class ExtractJsonTests(unittest.TestCase):
    def test_direct_json(self):
        report = make_report()
        self.assertEqual(ar.extract_json(ar.json.dumps(report)), report)

    def test_fenced_json(self):
        report = make_report()
        text = f"```json\n{ar.json.dumps(report)}\n```"
        self.assertEqual(ar.extract_json(text), report)

    def test_wrapped_structured_output(self):
        report = make_report()
        text = ar.json.dumps({"structured_output": report})
        self.assertEqual(ar.extract_json(text), report)

    def test_wrapped_result_string(self):
        report = make_report()
        text = ar.json.dumps({"result": ar.json.dumps(report)})
        self.assertEqual(ar.extract_json(text), report)

    def test_jsonl_events(self):
        report = make_report()
        lines = [
            ar.json.dumps({"type": "status"}),
            ar.json.dumps({"data": {"content": "thinking..."}}),
            ar.json.dumps({"result": ar.json.dumps(report)}),
        ]
        self.assertEqual(ar.extract_json("\n".join(lines)), report)

    def test_empty_output_raises(self):
        with self.assertRaises(SystemExit):
            ar.extract_json("   ")

    def test_unexpected_shape_raises(self):
        with self.assertRaises(SystemExit):
            ar.extract_json(ar.json.dumps({"unrelated": True}))


class ValidateShapeTests(unittest.TestCase):
    def test_valid_report_passes(self):
        ar.validate_shape(make_report(findings=[make_finding()]))

    def test_missing_required_key_raises(self):
        report = make_report()
        del report["overall_confidence"]
        with self.assertRaises(SystemExit):
            ar.validate_shape(report)

    def test_unexpected_top_level_key_raises(self):
        with self.assertRaises(SystemExit):
            ar.validate_shape(make_report(extra="nope"))

    def test_invalid_overall_correctness_raises(self):
        with self.assertRaises(SystemExit):
            ar.validate_shape(make_report(overall_correctness="maybe"))

    def test_finding_unexpected_key_raises(self):
        with self.assertRaises(SystemExit):
            ar.validate_shape(make_report(findings=[make_finding(extra="nope")]))

    def test_finding_invalid_priority_raises(self):
        with self.assertRaises(SystemExit):
            ar.validate_shape(make_report(findings=[make_finding(priority="P9")]))

    def test_finding_absolute_path_raises(self):
        with self.assertRaises(SystemExit):
            ar.validate_shape(
                make_report(findings=[make_finding(code_location={"file_path": "/etc/passwd", "line": 1})])
            )

    def test_finding_path_traversal_raises(self):
        with self.assertRaises(SystemExit):
            ar.validate_shape(
                make_report(findings=[make_finding(code_location={"file_path": "../secret.py", "line": 1})])
            )


class FilterInScopeFindingsTests(unittest.TestCase):
    def test_splits_kept_and_ignored(self):
        in_scope = make_finding(code_location={"file_path": "src/app.py", "line": 1})
        out_of_scope = make_finding(code_location={"file_path": "src/other.py", "line": 2})
        kept, ignored = ar.filter_in_scope_findings([in_scope, out_of_scope], {"src/app.py"})
        self.assertEqual(kept, [in_scope])
        self.assertEqual([item[1] for item in ignored], [out_of_scope])


class ValidateReportTests(unittest.TestCase):
    def test_drops_out_of_scope_and_flips_correctness_when_all_dropped(self):
        finding = make_finding(code_location={"file_path": "src/other.py", "line": 1})
        report = make_report(overall_correctness="patch is incorrect", findings=[finding])
        ar.validate_report(report, changed_paths={"src/app.py"}, required=[])
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["overall_correctness"], "patch is correct")
        self.assertIn("Ignored 1 out-of-scope", report["overall_explanation"])

    def test_keeps_in_scope_findings(self):
        finding = make_finding(code_location={"file_path": "src/app.py", "line": 1})
        report = make_report(overall_correctness="patch is incorrect", findings=[finding])
        ar.validate_report(report, changed_paths={"src/app.py"}, required=[])
        self.assertEqual(report["findings"], [finding])
        self.assertEqual(report["overall_correctness"], "patch is incorrect")

    def test_required_finding_text_missing_raises(self):
        report = make_report(findings=[make_finding(body="unrelated body text")])
        with self.assertRaises(SystemExit):
            ar.validate_report(report, changed_paths={"src/app.py"}, required=["sql injection"])

    def test_required_finding_text_present_passes(self):
        finding = make_finding(code_location={"file_path": "src/app.py", "line": 1}, body="classic sql injection here")
        report = make_report(findings=[finding])
        ar.validate_report(report, changed_paths={"src/app.py"}, required=["sql injection"])


class MergePanelReportsTests(unittest.TestCase):
    def test_deduplicates_identical_findings_across_reviewers(self):
        finding = make_finding()
        reports = [
            ("claude", make_report(findings=[finding])),
            ("codex", make_report(findings=[dict(finding)])),
        ]
        merged = ar.merge_panel_reports(reports)
        self.assertEqual(len(merged["findings"]), 1)
        self.assertIn("Reviewer:", merged["findings"][0]["body"])

    def test_keeps_distinct_findings_and_marks_incorrect(self):
        a = make_finding(title="Finding A")
        b = make_finding(title="Finding B", code_location={"file_path": "src/other.py", "line": 5})
        reports = [
            ("claude", make_report(findings=[a])),
            ("codex", make_report(findings=[b])),
        ]
        merged = ar.merge_panel_reports(reports)
        self.assertEqual(len(merged["findings"]), 2)
        self.assertEqual(merged["overall_correctness"], "patch is incorrect")

    def test_clean_panel_stays_correct(self):
        reports = [("claude", make_report()), ("codex", make_report())]
        merged = ar.merge_panel_reports(reports)
        self.assertEqual(merged["findings"], [])
        self.assertEqual(merged["overall_correctness"], "patch is correct")


class ReviewerSpecParsingTests(unittest.TestCase):
    def test_parse_reviewer_token_engine_only(self):
        self.assertEqual(ar.parse_reviewer_token("codex"), ("codex", None, None))

    def test_parse_reviewer_token_full(self):
        self.assertEqual(ar.parse_reviewer_token("codex:gpt-5.1:high"), ("codex", "gpt-5.1", "high"))

    def test_parse_reviewer_token_unknown_engine_raises(self):
        with self.assertRaises(SystemExit):
            ar.parse_reviewer_token("bogus:model:high")

    def test_parse_reviewer_token_too_many_parts_raises(self):
        with self.assertRaises(SystemExit):
            ar.parse_reviewer_token("codex:a:b:c")

    def test_parse_keyed_options_global_and_per_engine(self):
        global_value, per_engine = ar.parse_keyed_options(["high", "claude=max"], "thinking")
        self.assertEqual(global_value, "high")
        self.assertEqual(per_engine, {"claude": "max"})

    def test_parse_keyed_options_duplicate_engine_raises(self):
        with self.assertRaises(SystemExit):
            ar.parse_keyed_options(["claude=high", "claude=low"], "thinking")

    def test_parse_keyed_options_duplicate_global_raises(self):
        with self.assertRaises(SystemExit):
            ar.parse_keyed_options(["high", "low"], "thinking")


class NumberInRangeTests(unittest.TestCase):
    def test_accepts_boundary_values(self):
        self.assertTrue(ar.number_in_range(0))
        self.assertTrue(ar.number_in_range(1))
        self.assertTrue(ar.number_in_range(0.5))

    def test_rejects_out_of_range_and_bool(self):
        self.assertFalse(ar.number_in_range(1.1))
        self.assertFalse(ar.number_in_range(-0.1))
        self.assertFalse(ar.number_in_range(True))
        self.assertFalse(ar.number_in_range("0.5"))


class BoundedFieldTests(unittest.TestCase):
    def test_short_text_untouched(self):
        self.assertEqual(ar.bounded_field("hello", 100), "hello")

    def test_long_text_truncated_with_suffix(self):
        result = ar.bounded_field("x" * 50, 20)
        self.assertLessEqual(len(result), 20)
        self.assertTrue(result.endswith("[truncated]"))


class CommandSandboxTests(unittest.TestCase):
    """resolve_command/find_command are the security boundary that keeps a
    reviewed (untrusted) checkout from shadowing git/gh/the review engine via a
    PATH entry inside the repo. Exercises that boundary directly."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        self.outside = Path(self.tmp.name) / "outside-bin"
        self.outside.mkdir()

    def _make_executable(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\necho hi\n")
        path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        return path

    def test_rejects_executable_shadowed_from_a_path_entry_inside_the_repo(self):
        hostile = self._make_executable(self.repo / "bin" / "git")
        with mock.patch.dict(os.environ, {"PATH": str(hostile.parent)}):
            self.assertIsNone(ar.find_command("git", self.repo))

    def test_finds_executable_from_a_path_entry_outside_the_repo(self):
        real = self._make_executable(self.outside / "git")
        with mock.patch.dict(os.environ, {"PATH": str(real.parent)}):
            # find_command resolves PATH entries (Path.resolve()) before matching,
            # so compare against the resolved path (e.g. /var -> /private/var on macOS).
            self.assertEqual(ar.find_command("git", self.repo), str(real.resolve()))

    def test_ignores_relative_and_dot_path_entries(self):
        with mock.patch.dict(os.environ, {"PATH": ".:relative/dir"}):
            self.assertIsNone(ar.find_command("git", self.repo))

    def test_explicit_relative_bin_resolves_from_repo_root(self):
        tool = self._make_executable(self.repo / "tools" / "codex")
        with mock.patch.dict(os.environ, {"PATH": ""}):
            self.assertEqual(ar.find_command("tools/codex", self.repo), str(tool))

    def test_resolve_command_raises_when_nothing_found(self):
        with mock.patch.dict(os.environ, {"PATH": ""}):
            with self.assertRaises(SystemExit):
                ar.resolve_command("totally-not-a-real-binary", self.repo)


if __name__ == "__main__":
    unittest.main()
