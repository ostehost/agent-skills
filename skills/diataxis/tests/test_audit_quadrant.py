#!/usr/bin/env python3
"""Fixture, mutation, coverage, self-audit, and CLI tests for audit_quadrant.py.

Run from the repository root:

    python3 -m unittest skills.diataxis.tests.test_audit_quadrant

Every rule has a negative fixture or a mutation that turns red when the forbidden
state is introduced; the coverage meta-test fails when a new rule arrives without one.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SKILL = TESTS.parent
SCRIPT = SKILL / "scripts" / "audit_quadrant.py"
FIXTURES = TESTS / "fixtures"
SKILL_FILES = [SKILL / "SKILL.md"] + sorted((SKILL / "references").glob("*.md"))


def load_module():
    spec = importlib.util.spec_from_file_location("audit_quadrant_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module()


def run(*args: object, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *(str(a) for a in args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        cwd=str(cwd) if cwd else None,
        check=False,
    )


def audit_json(*args: object, cwd: Path | None = None) -> tuple[int, dict]:
    proc = run("--format", "json", *args, cwd=cwd)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as error:  # pragma: no cover - diagnostic path
        raise AssertionError(f"no JSON on stdout (exit {proc.returncode}): {proc.stderr}") from error
    return proc.returncode, data


def rules_of(data: dict, index: int = 0) -> list[str]:
    return [f["rule"] for f in data["files"][index]["findings"]]


CLEAN = {q: FIXTURES / "clean" / f"{q}.md" for q in MODULE.QUADRANTS}
CLEAN["landing"] = FIXTURES / "clean" / "landing" / "README.md"

EXPECTED_BLEED = {
    "exp-procedure-list", "exp-terminal-steps", "exp-procedure-heading", "exp-imperative-prose",
    "exp-option-table",
    "ref-procedure", "ref-opinion", "ref-narrative-voice", "ref-why-digression", "ref-narrative-paragraph",
    "ref-hedge", "ref-marketing",
    "tut-choice", "tut-explanation-heading", "tut-why-digression", "tut-reference-dump", "tut-learning-claim",
    "tut-reads-as-howto",
    "howto-teaching-tone", "howto-concept-heading", "howto-explanation-block", "howto-option-table",
    "howto-title",
    "landing-long-list", "landing-bare-list", "landing-quadrant-content",
    "declaration-invalid", "declaration-conflict", "declared-inferred-mismatch", "mixed-undeclared",
}

OPTION_TABLE = (
    "\n| Option | Type | Default |\n|---|---|---|\n| a | string | x |\n| b | string | x |\n"
    "| c | string | x |\n| d | string | x |\n| e | string | x |\n| f | string | x |\n"
)

# Each content rule -> (clean fixture quadrant, snippet appended to that fixture).
MUTATIONS: dict[str, tuple[str, str]] = {
    "exp-procedure-list": ("explanation", "\n1. Run `make build`.\n2. Open the config file.\n3. Restart the service.\n"),
    "exp-terminal-steps": ("explanation", "\nTo try it, run the build:\n\n```bash\nmake build\n```\n"),
    "exp-procedure-heading": ("explanation", "\n## Installation\n\nThe package ships as a wheel.\n"),
    "exp-imperative-prose": ("explanation", "\nOpen the config file. Set the cache size to 512. Restart the service.\n"),
    "exp-option-table": ("explanation", OPTION_TABLE),
    "ref-procedure": ("reference", "\n1. Open the dashboard.\n2. Click **Tokens**.\n3. Copy the token.\n"),
    "ref-opinion": ("reference", "\nI recommend this layout.\n"),
    "ref-narrative-voice": ("reference", "\nOur team maintains this command.\n"),
    "ref-why-digression": ("reference", "\nThe limit is 50 because the API caps batches. Historically, the cap was lower.\n"),
    "ref-narrative-paragraph": ("reference", "\nIt has one mode. It reads stdin. It writes stdout. It logs to stderr. It exits 0.\n"),
    "ref-hedge": ("reference", "\nThe call might time out.\n"),
    "ref-marketing": ("reference", "\nThis is the fastest client available.\n"),
    "tut-choice": ("tutorial", "\nAlternatively, you can use the web console.\n"),
    "tut-explanation-heading": ("tutorial", "\n## How it works\n\nThe dashboard polls the API.\n"),
    "tut-why-digression": ("tutorial", "\nThe page refreshes every minute. That happens because the scheduler wakes on a fixed tick.\n"),
    "tut-reference-dump": ("tutorial", OPTION_TABLE),
    "tut-learning-claim": ("tutorial", "\nNext, you will learn how caching works.\n"),
    "howto-teaching-tone": ("how-to", "\nDon't worry if this step fails the first time.\n"),
    "howto-concept-heading": ("how-to", "\n## What is a key scope\n\nA scope limits a key.\n"),
    "howto-explanation-block": ("how-to", "\nKeys expire after ninety days. The expiry limits leaked keys. Expired keys return errors.\n"),
    "howto-option-table": ("how-to", OPTION_TABLE),
    "howto-title": ("how-to", "\n# Key rotation\n\nRotate keys every quarter.\n"),
    "landing-long-list": ("landing", "\nOlder pages:\n\n- zeta\n- alpha\n- gamma\n- beta\n- eta\n- delta\n- theta\n- iota\n"),
    "landing-bare-list": ("landing", "\n## Archive\n\n- [Old page](old.md)\n"),
    "landing-quadrant-content": ("landing", "\nEvery setting at a glance:\n" + OPTION_TABLE),
}

# File-level absence rules cannot be provoked by appending text; a bleed fixture covers them.
FILE_LEVEL_RULES = {"tut-reads-as-howto"}
CONTENT_PREFIXES = ("exp-", "ref-", "tut-", "howto-", "landing-")
SUPPRESSION_COVERED = {"suppression-unknown-rule", "suppression-unused", "suppression-unterminated"}
PATHS_COVERED = {"layout-empty-quadrant"}


class CleanFixtures(unittest.TestCase):
    def test_clean_quadrant_fixtures_pass_strict_and_infer_themselves(self) -> None:
        for quadrant in MODULE.QUADRANTS:
            with self.subTest(quadrant=quadrant):
                code, data = audit_json("--strict", CLEAN[quadrant])
                record = data["files"][0]
                self.assertEqual(code, 0, record["findings"])
                self.assertEqual(record["findings"], [])
                self.assertEqual(record["declared"], {"quadrant": quadrant, "source": "frontmatter"})
                self.assertGreaterEqual(record["words"], MODULE.MIN_WORDS_FOR_INFERENCE)
                self.assertEqual(record["inferred"], quadrant)

    def test_clean_landing_readme_passes_strict(self) -> None:
        code, data = audit_json("--strict", CLEAN["landing"])
        self.assertEqual(code, 0, data["files"][0]["findings"])
        self.assertEqual(data["files"][0]["declared"], {"quadrant": "landing", "source": "filename"})


class BleedFixtures(unittest.TestCase):
    def test_bleed_fixture_set_is_complete(self) -> None:
        stems = {p.stem for p in (FIXTURES / "bleed").glob("*.md")}
        self.assertEqual(stems, EXPECTED_BLEED)

    def test_each_bleed_fixture_fires_its_rule(self) -> None:
        for path in sorted((FIXTURES / "bleed").glob("*.md")):
            rule = path.stem
            with self.subTest(rule=rule):
                code, data = audit_json("--strict", path)
                findings = [f for f in data["files"][0]["findings"] if f["rule"] == rule]
                self.assertTrue(findings, f"{rule} did not fire: {rules_of(data)}")
                self.assertEqual(code, 1)
                default_code, _ = audit_json(path)
                expect_major = any(f["severity"] == "major" for f in findings)
                if expect_major:
                    self.assertEqual(default_code, 1)
                if MODULE.RULES[rule].severity == "major":
                    self.assertTrue(expect_major)

    def test_three_imperatives_in_explanation_paragraph_is_major(self) -> None:
        _, data = audit_json(FIXTURES / "bleed" / "exp-imperative-prose.md")
        severities = [f["severity"] for f in data["files"][0]["findings"] if f["rule"] == "exp-imperative-prose"]
        self.assertEqual(severities, ["major"])

    def test_two_imperatives_in_explanation_paragraph_is_minor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "page.md"
            page.write_text("---\ndiataxis: explanation\n---\n\n# About x\n\nIntro.\n\n"
                            "Open the config file. Set the cache size to 512.\n", encoding="utf-8")
            code, data = audit_json(page)
            severities = [f["severity"] for f in data["files"][0]["findings"]]
            self.assertEqual(severities, ["minor"])
            self.assertEqual(code, 0)

    def test_repeated_tutorial_digression_escalates_to_major(self) -> None:
        code, data = audit_json(FIXTURES / "bleed" / "tut-why-digression.md")
        findings = [f for f in data["files"][0]["findings"] if f["rule"] == "tut-why-digression"]
        self.assertEqual(len(findings), MODULE.FILE_ESCALATION_COUNT)
        self.assertTrue(all(f["severity"] == "major" for f in findings))
        self.assertEqual(code, 1)


class NearMissFixtures(unittest.TestCase):
    def test_near_misses_do_not_fire_their_rule(self) -> None:
        for path in sorted((FIXTURES / "nearmiss").glob("*.md")):
            rule = path.stem.split("--")[0]
            if rule == "example-region-hides":
                rule = "exp-procedure-list"
            with self.subTest(fixture=path.name):
                self.assertIn(rule, MODULE.RULES)
                code, data = audit_json("--strict", path)
                self.assertNotIn(rule, rules_of(data))
                self.assertEqual(code, 0, rules_of(data))
                self.assertEqual(data["files"][0]["suppressed"], [])


class DirectiveFixtures(unittest.TestCase):
    def check(self, name: str) -> tuple[int, dict]:
        return audit_json("--strict", "--check-directives", FIXTURES / "directives" / f"{name}.md")

    def test_clean_directives_pass(self) -> None:
        code, data = self.check("clean")
        self.assertEqual((code, rules_of(data)), (0, []))

    def test_each_directive_fixture_fires_its_rule(self) -> None:
        for path in sorted((FIXTURES / "directives").glob("dir-*.md")):
            with self.subTest(rule=path.stem):
                code, data = self.check(path.stem)
                self.assertIn(path.stem, rules_of(data))
                self.assertEqual(code, 1)

    def test_word_count_flags_long_and_short_bullets(self) -> None:
        _, data = self.check("dir-word-count")
        matches = [f["match"] for f in data["files"][0]["findings"] if f["rule"] == "dir-word-count"]
        self.assertEqual(len(matches), 2)
        self.assertTrue(matches[0].startswith("14 words"))
        self.assertTrue(matches[1].startswith("6 words"))

    def test_every_legacy_prompt_pattern_is_caught(self) -> None:
        _, data = self.check("dir-legacy-prompt")
        lines = {f["line"] for f in data["files"][0]["findings"] if f["rule"] == "dir-legacy-prompt"}
        self.assertEqual(len(lines), 10)

    def test_structure_flags_missing_section_prose_and_nested_bullet(self) -> None:
        _, data = self.check("dir-structure")
        matches = " | ".join(f["match"] for f in data["files"][0]["findings"] if f["rule"] == "dir-structure")
        self.assertIn("missing `## Do not` section", matches)
        self.assertIn("prose inside a directive section", matches)
        self.assertIn("nested bullet is not `Why:`", matches)

    def test_directive_rules_are_not_suppressible(self) -> None:
        for rule_id, rule in MODULE.RULES.items():
            if rule_id.startswith(MODULE.UNSUPPRESSIBLE_PREFIXES):
                self.assertFalse(rule.suppressible, rule_id)
                self.assertEqual(rule.severity, "major" if rule_id != "suppression-unused" else "minor")


class SuppressionFixtures(unittest.TestCase):
    def fixture(self, name: str, *flags: str) -> tuple[int, dict]:
        return audit_json("--strict", *flags, FIXTURES / "suppression" / f"{name}.md")

    def test_valid_suppression(self) -> None:
        code, data = self.fixture("valid")
        self.assertEqual(code, 0, rules_of(data))
        self.assertEqual(len(data["files"][0]["suppressed"]), 1)
        self.assertEqual(data["summary"]["suppressed"], 1)

    def test_unknown_rule(self) -> None:
        code, data = self.fixture("unknown-rule")
        self.assertIn("suppression-unknown-rule", rules_of(data))
        self.assertEqual(code, 1)

    def test_unused(self) -> None:
        code, data = self.fixture("unused")
        self.assertEqual(rules_of(data), ["suppression-unused"])
        self.assertEqual(code, 1)

    def test_unterminated_example_region_fails_closed(self) -> None:
        code, data = self.fixture("unterminated")
        rules = rules_of(data)
        self.assertIn("suppression-unterminated", rules)
        self.assertIn("exp-procedure-heading", rules)
        self.assertEqual(code, 1)

    def test_directive_rule_cannot_be_suppressed(self) -> None:
        code, data = self.fixture("not-suppressible", "--check-directives")
        rules = rules_of(data)
        self.assertIn("suppression-unknown-rule", rules)
        self.assertIn("dir-word-count", rules)
        self.assertEqual(data["files"][0]["suppressed"], [])
        self.assertEqual(code, 1)

    def test_file_wide_suppression(self) -> None:
        code, data = self.fixture("file-wide")
        self.assertEqual(code, 0, rules_of(data))
        suppressed = [f["rule"] for f in data["files"][0]["suppressed"]]
        self.assertEqual(suppressed, ["exp-imperative-prose", "exp-imperative-prose"])

    def test_example_region_hides_content_but_not_directives(self) -> None:
        code, data = self.fixture("example-region", "--check-directives")
        self.assertEqual(rules_of(data), ["dir-shouting"])
        self.assertEqual(code, 1)
        code, data = self.fixture("example-region")
        self.assertEqual((code, rules_of(data)), (0, []))


class PathFixtures(unittest.TestCase):
    def test_path_declares_quadrant(self) -> None:
        _, data = audit_json(FIXTURES / "paths" / "docs" / "how-to" / "rotate-keys.md")
        record = data["files"][0]
        self.assertEqual(record["declared"], {"quadrant": "how-to", "source": "path"})
        self.assertIn("howto-teaching-tone", rules_of(data))

    def test_filename_beats_path(self) -> None:
        _, data = audit_json(FIXTURES / "paths" / "docs" / "explanation" / "README.md")
        self.assertEqual(data["files"][0]["declared"], {"quadrant": "landing", "source": "filename"})

    def test_plural_references_directory_is_not_a_quadrant(self) -> None:
        _, data = audit_json(FIXTURES / "paths" / "docs" / "references" / "notes.md")
        self.assertEqual(data["files"][0]["declared"], {"quadrant": "none", "source": "none"})

    def test_index_page_holding_a_procedure_is_flagged(self) -> None:
        code, data = audit_json("--strict", FIXTURES / "paths" / "docs" / "how-to" / "backups" / "index.md")
        record = data["files"][0]
        self.assertEqual(record["declared"], {"quadrant": "landing", "source": "filename"})
        matches = [f["match"] for f in record["findings"] if f["rule"] == "landing-quadrant-content"]
        self.assertEqual(len(matches), 2, record["findings"])
        self.assertEqual(code, 1)

    def test_index_only_quadrant_directory_is_empty(self) -> None:
        code, data = audit_json(FIXTURES / "paths" / "docs")
        flagged = {Path(item["path"]).name for item in data["layout"] if item["rule"] == "layout-empty-quadrant"}
        self.assertIn("tutorials", flagged)
        self.assertNotIn("how-to", flagged)
        self.assertNotIn("references", flagged)
        self.assertEqual(code, 1)

    def test_file_stem_never_declares(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "tutorial.md"
            page.write_text("# Notes\n\nPlain notes.\n", encoding="utf-8")
            _, data = audit_json(page)
            self.assertEqual(data["files"][0]["declared"]["source"], "none")


class Mutations(unittest.TestCase):
    def test_mutations_cover_every_content_rule(self) -> None:
        content = {r for r in MODULE.RULES if r.startswith(CONTENT_PREFIXES)} - FILE_LEVEL_RULES
        self.assertEqual(set(MUTATIONS), content)

    def test_each_mutation_turns_the_clean_fixture_red(self) -> None:
        for rule, (quadrant, snippet) in MUTATIONS.items():
            with self.subTest(rule=rule), tempfile.TemporaryDirectory() as tmp:
                source = CLEAN[quadrant]
                target = Path(tmp) / source.name
                original = source.read_text(encoding="utf-8")
                target.write_text(original, encoding="utf-8")
                code, data = audit_json("--strict", target)
                self.assertEqual((code, rules_of(data)), (0, []), f"unmutated {quadrant} fixture is not clean")
                target.write_text(original + snippet, encoding="utf-8")
                code, data = audit_json("--strict", target)
                self.assertIn(rule, rules_of(data))
                self.assertEqual(code, 1)


class Coverage(unittest.TestCase):
    def test_every_rule_has_a_negative_fixture_or_mutation(self) -> None:
        bleed = {p.stem for p in (FIXTURES / "bleed").glob("*.md")}
        directives = {p.stem for p in (FIXTURES / "directives").glob("dir-*.md")}
        covered = bleed | set(MUTATIONS) | directives | SUPPRESSION_COVERED | PATHS_COVERED
        missing = set(MODULE.RULES) - covered
        self.assertEqual(missing, set(), f"rules without a negative fixture: {sorted(missing)}")


class SkillSelfAudit(unittest.TestCase):
    def test_skill_files_have_zero_bleed(self) -> None:
        code, data = audit_json("--strict", "--check-directives", *SKILL_FILES)
        self.assertEqual(code, 0, [(f["path"], f["findings"]) for f in data["files"]])
        self.assertEqual(data["summary"], {"files": 5, "major": 0, "minor": 0, "suppressed": 0})
        for record in data["files"]:
            self.assertEqual(record["suppressed"], [])
            expected = "how-to" if record["path"].endswith("SKILL.md") else "reference"
            self.assertEqual(record["declared"], {"quadrant": expected, "source": "marker"})

    def test_skill_files_use_no_suppressions_or_example_regions(self) -> None:
        for path in SKILL_FILES:
            doc = MODULE.parse_document(path.read_text(encoding="utf-8"))
            self.assertEqual(doc.suppressions, [], path.name)
            self.assertFalse(any(b.sub == "hidden-example" for b in doc.blocks), path.name)

    def test_reference_files_stay_short(self) -> None:
        for path in SKILL_FILES[1:]:
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertLessEqual(len(lines), 100, path.name)
            self.assertEqual(lines[0], "<!-- diataxis: reference -->")

    def mutate(self, path: Path, transform) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / path.name
            target.write_text(transform(path.read_text(encoding="utf-8")), encoding="utf-8")
            return audit_json("--strict", "--check-directives", target)

    def test_legacy_prompt_in_skill_turns_red(self) -> None:
        bullet = "- Think step-by-step before classifying the asset now please.\n"
        code, data = self.mutate(SKILL_FILES[0], lambda s: s.replace("## Do\n\n", "## Do\n\n" + bullet, 1))
        self.assertIn("dir-legacy-prompt", rules_of(data))
        self.assertEqual(code, 1)

    def test_opinion_in_reference_file_turns_red(self) -> None:
        code, data = self.mutate(SKILL.joinpath("references", "reference.md"),
                                 lambda s: s + "\nI recommend this layout.\n")
        self.assertIn("ref-opinion", rules_of(data))
        self.assertEqual(code, 1)

    def test_long_workflow_step_in_skill_turns_red(self) -> None:
        step = "3. Print the completed receipt before the first write to each asset.\n"
        longer = "3. Print the completed receipt in your response before the first write to each asset.\n"
        code, data = self.mutate(SKILL_FILES[0], lambda s: s.replace(step, longer, 1))
        self.assertIn("dir-word-count", rules_of(data))
        self.assertEqual(code, 1)

    def test_noun_led_layout_bullet_in_skill_turns_red(self) -> None:
        bullet = "- Create `docs/<quadrant>/` only together with its first real page.\n"
        noun_led = "- Quadrant directories appear only together with their first real page.\n"
        code, data = self.mutate(SKILL_FILES[0], lambda s: s.replace(bullet, noun_led, 1))
        self.assertIn("dir-verb", rules_of(data))
        self.assertEqual(code, 1)

    def test_long_directive_in_skill_turns_red(self) -> None:
        bullet = "- Run the strict audit on every touched file before you report the task done.\n"
        code, data = self.mutate(SKILL_FILES[0], lambda s: s.replace("## Do\n\n", "## Do\n\n" + bullet, 1))
        self.assertIn("dir-word-count", rules_of(data))
        self.assertEqual(code, 1)

    def test_skill_links_each_reference_one_level_deep(self) -> None:
        text = SKILL_FILES[0].read_text(encoding="utf-8")
        links = set(re.findall(r"\]\((references/[^)]+)\)", text))
        expected = {f"references/{p.name}" for p in SKILL_FILES[1:]}
        self.assertEqual(links, expected)
        for link in links:
            self.assertTrue((SKILL / link).is_file(), link)
            self.assertEqual(len(Path(link).parts), 2, link)

    def test_frontmatter_has_only_name_and_description(self) -> None:
        text = SKILL_FILES[0].read_text(encoding="utf-8")
        block = text.split("---\n")[1]
        keys = [line.split(":")[0] for line in block.splitlines() if line and not line.startswith(" ")]
        self.assertEqual(keys, ["name", "description"])
        description = re.search(r'^description: "(.*)"$', block, re.M)
        self.assertIsNotNone(description)
        self.assertLessEqual(len(description.group(1)), 180)


class Cli(unittest.TestCase):
    def assert_usage_error(self, *args: object, cwd: Path | None = None) -> None:
        proc = run(*args, cwd=cwd)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertTrue(proc.stderr.startswith("audit_quadrant: "), proc.stderr)

    def test_usage_and_io_errors_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty"
            empty.mkdir()
            self.assert_usage_error(Path(tmp) / "missing.md")
            self.assert_usage_error("--quadrant", "bogus", CLEAN["tutorial"])
            self.assert_usage_error(empty)
            self.assert_usage_error("--receipt", CLEAN["tutorial"])
            self.assert_usage_error("--receipt", "--operation", "edit", Path(tmp) / "missing.md")
            self.assert_usage_error("--receipt", "--plan", "--operation", "edit", CLEAN["tutorial"])
            self.assert_usage_error("--no-such-flag", CLEAN["tutorial"])

    def test_missing_path_error_is_one_line(self) -> None:
        proc = run("definitely-missing.md")
        self.assertEqual(proc.stderr.strip().count("\n"), 0)
        self.assertEqual(proc.stderr.strip(), "audit_quadrant: definitely-missing.md: no such file or directory")

    def test_io_error_wins_but_other_files_are_audited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.md"
            bad.write_bytes(b"# Bad\n\n\xff\xfe not utf-8\n")
            code, data = audit_json(bad, FIXTURES / "bleed" / "ref-marketing.md")
            self.assertEqual(code, 2)
            self.assertEqual(len(data["files"]), 1)
            self.assertIn("not valid UTF-8", data["errors"][0]["reason"])

    def test_json_output_schema(self) -> None:
        code, data = audit_json(*CLEAN.values())
        self.assertEqual(code, 0)
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["exit_code"], 0)
        self.assertEqual(set(data["summary"]), {"files", "major", "minor", "suppressed"})
        record = data["files"][0]
        self.assertEqual(set(record), {"path", "declared", "inferred", "challenger", "words", "signals",
                                       "findings", "suppressed"})

    def test_text_summary_line(self) -> None:
        proc = run(FIXTURES / "bleed" / "exp-terminal-steps.md")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("major exp-terminal-steps:", proc.stdout)
        self.assertIn("audited 1 files: 1 major, 0 minor, 0 suppressed; exit 1", proc.stdout)

    def test_receipt_for_new_asset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = run("--receipt", "--operation", "create", "docs/how-to/new.md", cwd=Path(tmp))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            receipt = json.loads(proc.stdout)
            self.assertEqual(receipt["receipt"], "diataxis/quadrant-classification")
            self.assertEqual(receipt["declared"], {"quadrant": "how-to", "source": "path"})
            self.assertEqual(receipt["strongest_alternative"], {"quadrant": "tutorial", "rejected_because": None})
            for key in ("reader_need", "quadrant", "confidence", "decision"):
                self.assertIsNone(receipt[key], key)
            self.assertEqual(receipt["compass"], {"informs": None, "serves": None})
            self.assertEqual(receipt["split_plan"], [])
            self.assertIsNone(receipt["destination"])
            self.assertIsNone(receipt["handoff"])
            self.assertTrue(receipt["audit_command"].endswith("--strict docs/how-to/new.md"))
            self.assertFalse((Path(tmp) / "docs").exists())

    def test_receipt_prefills_findings_and_challenger(self) -> None:
        proc = run("--receipt", "--operation", "edit", FIXTURES / "bleed" / "declared-inferred-mismatch.md")
        receipt = json.loads(proc.stdout)
        self.assertEqual(receipt["inferred"], "explanation")
        self.assertEqual(receipt["strongest_alternative"]["quadrant"], "explanation")
        self.assertIn("declared-inferred-mismatch", receipt["contamination_risks"])

    def test_receipt_on_readme_hands_off(self) -> None:
        proc = run("--receipt", "--operation", "edit", CLEAN["landing"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        receipt = json.loads(proc.stdout)
        self.assertEqual(receipt["handoff"], "readme-standard")
        self.assertEqual(receipt["declared"]["quadrant"], "landing")

    def test_plan_reuses_existing_directory_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "docs"
            (root / "how-to-guides").mkdir(parents=True)
            (root / "how-to-guides" / "existing.md").write_text(
                CLEAN["how-to"].read_text(encoding="utf-8"), encoding="utf-8")
            body = CLEAN["how-to"].read_text(encoding="utf-8").split("---\n", 2)[2]
            (root / "rotate.md").write_text(body, encoding="utf-8")
            before = sorted(str(p) for p in root.rglob("*"))
            code, data = audit_json("--plan", root)
            after = sorted(str(p) for p in root.rglob("*"))
            self.assertEqual(code, 0)
            self.assertEqual(before, after)
            entries = {Path(e["path"]).name: e for e in data["files"]}
            self.assertEqual(entries["rotate.md"]["action"], "move")
            self.assertEqual(entries["rotate.md"]["inferred"], "how-to")
            self.assertTrue(entries["rotate.md"]["proposed_path"].endswith("docs/how-to-guides/rotate.md"))
            self.assertEqual(entries["existing.md"]["action"], "keep")
            self.assertFalse((root / "how-to").exists())

    def test_list_rules_lists_every_rule(self) -> None:
        proc = run("--list-rules")
        self.assertEqual(proc.returncode, 0)
        listed = {line.split("\t")[0] for line in proc.stdout.splitlines()}
        self.assertEqual(listed, set(MODULE.RULES))
        proc = run("--list-rules", "--format", "json")
        self.assertEqual({r["id"] for r in json.loads(proc.stdout)}, set(MODULE.RULES))

    def test_glob_argument_is_expanded(self) -> None:
        code, data = audit_json(str(FIXTURES / "clean" / "*.md"))
        self.assertEqual(code, 0)
        self.assertEqual(len(data["files"]), 4)

    def test_non_ascii_path_and_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "café"
            folder.mkdir()
            page = folder / "über.md"
            page.write_text("---\ndiataxis: reference\n---\n\n# Diátaxis naïve entry\n\nTakes `ß`.\n",
                            encoding="utf-8")
            proc = run("--strict", page)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            proc = run("--strict", "--quadrant", "explanation", page)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("Error", proc.stderr)

    def test_crlf_and_bom_are_handled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "page.md"
            text = CLEAN["explanation"].read_text(encoding="utf-8").replace("\n", "\r\n")
            page.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
            code, data = audit_json("--strict", page)
            self.assertEqual(code, 0, rules_of(data))
            self.assertEqual(data["files"][0]["declared"]["source"], "frontmatter")


class Helpers(unittest.TestCase):
    def test_imperative_detection(self) -> None:
        yes = ["Run `make build`.", "Open the config file.", "Then, restart the service.",
               "If you want logs, set the level to debug.", "**Copy** the key."]
        no = ["Type checking happens at build time.", "Set theory frames the types.",
              "Consider the cache.", "The workers load the key.", "Builds are slow."]
        for sentence in yes:
            self.assertTrue(MODULE.is_imperative(MODULE.mask_prose(sentence)), sentence)
        for sentence in no:
            self.assertFalse(MODULE.is_imperative(MODULE.mask_prose(sentence)), sentence)

    def test_quadrant_aliases(self) -> None:
        for alias, expected in (("tutorials", "tutorial"), ("howto", "how-to"), ("guides", "how-to"),
                                ("how-to-guide", "how-to"), ("explanations", "explanation"),
                                ("concepts", "explanation"), ("Reference", "reference")):
            self.assertEqual(MODULE.normalize_quadrant(alias), expected, alias)
        self.assertIsNone(MODULE.normalize_quadrant("references"))

    def test_toml_frontmatter_declares(self) -> None:
        doc = MODULE.parse_document('+++\ndiataxis = "how-to"\n+++\n\n# How to x\n')
        declared, findings = MODULE.declaration(Path("x.md"), doc, None)
        self.assertEqual(declared, {"quadrant": "how-to", "source": "frontmatter"})
        self.assertEqual(findings, [])

    def test_marker_outside_scan_window_is_ignored(self) -> None:
        text = "# Title\n\n" + "".join(f"Line {i}.\n\n" for i in range(12)) + "<!-- diataxis: how-to -->\n"
        doc = MODULE.parse_document(text)
        self.assertEqual(doc.markers, [])

    def test_comment_inside_inline_code_is_not_a_directive(self) -> None:
        doc = MODULE.parse_document("Use `<!-- diataxis-ignore: ref-hedge -->` to silence one block.\n")
        self.assertEqual(doc.suppressions, [])


def audit_page(name: str, text: str, *flags: object, cwd: Path | None = None) -> tuple[int, dict]:
    """Write one page to a fresh temporary directory and audit it with --strict."""
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / name
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(text, encoding="utf-8")
        return audit_json("--strict", *flags, page, cwd=cwd)


REF_HEAD = "---\ndiataxis: reference\n---\n\n# Widget API\n\n"
EXP_HEAD = "---\ndiataxis: explanation\n---\n\n# About caching\n\n"
OPINION = "I think this is the best and most powerful API. We recommend it.\n"
DIRECTIVE_TAIL = ("\n## Do\n\n- Write each directive as one bullet of eight to twelve words.\n"
                  "\n## Do not\n\n- Pad directives with filler words; cut them to the core action.\n")


class ParserRegressions(unittest.TestCase):
    """Each test reproduces a reviewed parser or detector bug and fails without its fix."""

    def assert_opinion_found(self, text: str) -> None:
        code, data = audit_page("page.md", text)
        self.assertIn("ref-opinion", rules_of(data))
        self.assertEqual(code, 1)

    def test_details_mention_in_inline_code_hides_nothing(self) -> None:
        self.assert_opinion_found(REF_HEAD + "Wrap optional content in a `<details>` element.\n\n" + OPINION)

    def test_unterminated_details_stays_audited(self) -> None:
        self.assert_opinion_found(REF_HEAD + "<details>\n\nCollapsed notes.\n\n" + OPINION)

    def test_nested_colon_containers_close_in_order(self) -> None:
        self.assert_opinion_found(REF_HEAD + ":::: note\n::: tip\nInner tip.\n:::\nOuter note.\n::::\n\n" + OPINION)

    def test_closed_details_still_hides_its_content(self) -> None:
        code, data = audit_page("page.md", REF_HEAD + "<details>\n\n" + OPINION + "\n</details>\n")
        self.assertEqual((code, rules_of(data)), (0, []))

    def test_lazy_blockquote_continuation_is_quoted(self) -> None:
        text = REF_HEAD + "> I think this is the best widget we have ever built,\nand we recommend it to everyone.\n"
        code, data = audit_page("page.md", text)
        self.assertEqual((code, rules_of(data)), (0, []))

    def test_indented_code_after_heading_is_code(self) -> None:
        text = "---\ndiataxis: reference\n---\n\n# Widget API\n    # we recommend the best settings\n    retries = 3\n"
        code, data = audit_page("page.md", text)
        self.assertEqual((code, rules_of(data)), (0, []))

    def test_comment_in_indented_code_neither_declares_nor_suppresses(self) -> None:
        text = ("Authors declare a page with a comment near the top:\n\n    <!-- diataxis: reference -->\n\n"
                "I think this approach is the best one we have. We recommend it.\n")
        code, data = audit_page("page.md", text)
        self.assertEqual(data["files"][0]["declared"], {"quadrant": "none", "source": "none"})
        self.assertEqual(code, 0)
        text = (REF_HEAD + "Silence a block like this:\n\n    <!-- diataxis-ignore: ref-opinion -->\n\n" + OPINION)
        code, data = audit_page("page.md", text)
        self.assertIn("ref-opinion", rules_of(data))
        self.assertEqual(data["files"][0]["suppressed"], [])

    def test_malformed_marker_is_invalid(self) -> None:
        code, data = audit_page("page.md", "<!-- diataxis: how to -->\n\n# Widget\n")
        self.assertIn("declaration-invalid", rules_of(data))
        self.assertEqual(code, 1)

    def test_setext_headings_are_headings(self) -> None:
        text = ("---\ndiataxis: tutorial\n---\n\n# Build a widget\n\nIn this tutorial, we build a widget.\n\n"
                "Background\n----------\n\nThe widget exists.\n")
        code, data = audit_page("page.md", text)
        self.assertIn("tut-explanation-heading", rules_of(data))
        self.assertEqual(code, 1)
        text = "---\ndiataxis: how-to\n---\n\nKey rotation\n============\n\nRotate keys every quarter.\n"
        _, data = audit_page("page.md", text)
        self.assertIn("howto-title", rules_of(data))

    def test_line_numbers_ignore_unicode_line_separators(self) -> None:
        text = REF_HEAD + "The widget\u2028renders\u000cframes.\n\nIt might fail.\n"
        _, data = audit_page("page.md", text)
        lines = [f["line"] for f in data["files"][0]["findings"] if f["rule"] == "ref-hedge"]
        expected = text.split("\n").index("It might fail.") + 1
        self.assertEqual(lines, [expected])

    def test_unterminated_fence_keeps_its_last_line(self) -> None:
        code, data = audit_page("page.md", EXP_HEAD + "To try it, run the build:\n\n```\n$ make all\n")
        self.assertIn("exp-terminal-steps", rules_of(data))
        self.assertEqual(code, 1)

    def test_short_table_separator_is_a_table(self) -> None:
        text = ("---\ndiataxis: tutorial\n---\n\n# Build\n\nIn this tutorial, we build.\n\n"
                "| Name | Type | Default |\n|-|-|-|\n| a | b | c |\n")
        _, data = audit_page("page.md", text)
        self.assertIn("tut-reference-dump", rules_of(data))

    def test_yaml_comment_after_the_noun_type_is_not_a_terminal_step(self) -> None:
        text = EXP_HEAD + "Every field carries a name and a type:\n\n```yaml\n# a field declaration\nname: string\n```\n"
        code, data = audit_page("page.md", text)
        self.assertEqual((code, rules_of(data)), (0, []))

    def test_type_with_an_object_still_leads_into_a_terminal_step(self) -> None:
        text = EXP_HEAD + "To enable it, type the following:\n\n```\n$ cachectl enable\n```\n"
        _, data = audit_page("page.md", text)
        self.assertIn("exp-terminal-steps", rules_of(data))

    def test_indented_shell_session_is_a_terminal_step(self) -> None:
        text = EXP_HEAD + "Run the following to enable it:\n\n    $ cachectl enable\n    $ cachectl status\n"
        code, data = audit_page("page.md", text)
        self.assertIn("exp-terminal-steps", rules_of(data))
        self.assertEqual(code, 1)

    def test_bulleted_command_list_is_a_procedure(self) -> None:
        text = EXP_HEAD + "To enable it:\n\n- Open the config file.\n- Set the cache size to 512.\n- Restart the service.\n"
        code, data = audit_page("page.md", text)
        self.assertIn("exp-procedure-list", rules_of(data))
        self.assertEqual(code, 1)

    def test_bulleted_list_of_reasons_is_not_a_procedure(self) -> None:
        text = EXP_HEAD + "Caches fail in three ways:\n\n- Values go stale.\n- Keys collide.\n- Memory runs out.\n"
        code, data = audit_page("page.md", text)
        self.assertEqual((code, rules_of(data)), (0, []))

    def test_landing_page_that_reads_as_another_quadrant_is_flagged(self) -> None:
        why = ("The reason the cache exists is latency, and the trade-off is memory. Historically, remote caches "
               "were slow because every read crossed the network. A local cache is analogous to a CPU cache: it "
               "keeps hot values close. Some users prefer a shared cache because it survives restarts. That "
               "design decision shaped every later feature of the service and its operators. Memory is cheap on "
               "laptops and small servers, so the local cache stays the default for most deployments today.\n")
        code, data = audit_page("README.md", "# Cachy\n\nCachy is a local cache.\n\n## Why a local cache?\n\n" + why)
        record = data["files"][0]
        self.assertEqual(record["declared"]["quadrant"], "landing")
        self.assertEqual(record["inferred"], "explanation")
        self.assertIn("declared-inferred-mismatch", rules_of(data))
        self.assertEqual(code, 1)


class PathRegressions(unittest.TestCase):
    def test_path_declaration_ignores_the_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "r2" / "docs" / "how-to"
            folder.mkdir(parents=True)
            (folder / "rotate.md").write_text("# How to rotate\n\nRotate the key.\n", encoding="utf-8")
            for cwd, arg in ((Path(tmp) / "r2", "docs/how-to/rotate.md"), (folder, "rotate.md"),
                             (folder, "../how-to/rotate.md")):
                with self.subTest(cwd=cwd, arg=arg):
                    _, data = audit_json(arg, cwd=cwd)
                    self.assertEqual(data["files"][0]["declared"], {"quadrant": "how-to", "source": "path"})

    def test_path_declaration_stops_at_the_repository_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "background" / "repo"
            (repo / ".git").mkdir(parents=True)
            (repo / "docs").mkdir()
            page = repo / "docs" / "page.md"
            page.write_text("# Page\n\nPlain notes.\n", encoding="utf-8")
            for cwd, arg in ((None, page), (repo, "docs/page.md")):
                with self.subTest(cwd=cwd):
                    _, data = audit_json(arg, cwd=cwd)
                    self.assertEqual(data["files"][0]["declared"], {"quadrant": "none", "source": "none"})

    def test_literal_file_name_with_glob_characters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "notes[1].md").write_text("# Notes\n\nPlain notes.\n", encoding="utf-8")
            code, data = audit_json("notes[1].md", cwd=Path(tmp))
            self.assertEqual(code, 0, data["errors"])
            self.assertEqual([f["path"] for f in data["files"]], ["notes[1].md"])

    def test_glob_skips_dependency_and_git_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ("docs/page.md", "node_modules/pkg/x.md", ".git/x.md"):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text("# Page\n\nPlain notes.\n", encoding="utf-8")
            _, data = audit_json("**/*.md", cwd=root)
            self.assertEqual([f["path"] for f in data["files"]], ["docs/page.md"])


class DirectiveRegressions(unittest.TestCase):
    def check(self, body: str) -> tuple[int, dict]:
        return audit_page("SKILL.md", "# Directive sample\n" + body, "--check-directives")

    def test_directive_that_starts_with_a_link(self) -> None:
        code, data = self.check("\n## Do\n\n- [Cite](https://diataxis.fr/) the framework page when you justify a quadrant.\n"
                                "\n## Do not\n\n- Pad directives with filler words; cut them to the core action.\n")
        self.assertEqual((code, rules_of(data)), (0, []))

    def test_lazy_continuation_belongs_to_the_directive(self) -> None:
        _, data = self.check("\n## Do\n\n- Write each directive as one bullet of eight to twelve\n"
                             "words, wrapped lazily onto a second line.\n"
                             "\n## Do not\n\n- Pad directives with filler words; cut them to the core action.\n")
        findings = data["files"][0]["findings"]
        self.assertEqual([f["rule"] for f in findings], ["dir-word-count"])
        self.assertTrue(findings[0]["match"].startswith("17 words"), findings[0]["match"])

    def test_multiline_comment_in_a_directive_section_is_not_prose(self) -> None:
        code, data = self.check("\n## Do\n\n- Write each directive as one bullet of eight to twelve words.\n"
                                "\n## Do not\n\n<!-- maintainer note:\nkeep this list short -->\n"
                                "- Pad directives with filler words; cut them to the core action.\n")
        self.assertEqual((code, rules_of(data)), (0, []))

    def test_semicolon_inside_inline_code_is_not_a_redirect(self) -> None:
        _, data = self.check("\n## Do\n\n- Write each directive as one bullet of eight to twelve words.\n"
                             "\n## Do not\n\n- Run commands like `rm -rf build; make` without a recorded receipt first.\n")
        self.assertIn("dir-redirect-missing", rules_of(data))

    def test_indented_code_is_exempt_from_shouting_and_legacy_prompts(self) -> None:
        code, data = self.check("\nAn old prompt, quoted:\n\n    # IMPORTANT: think step by step\n    retries = 3\n"
                                + DIRECTIVE_TAIL)
        self.assertEqual((code, rules_of(data)), (0, []))

    def test_legacy_prompt_variants(self) -> None:
        _, data = self.check("\nThink through this step by step.\n\nReason step by step.\n" + DIRECTIVE_TAIL)
        lines = [f["line"] for f in data["files"][0]["findings"] if f["rule"] == "dir-legacy-prompt"]
        self.assertEqual(lines, [3, 5])

    def test_list_items_outside_do_sections_are_directives(self) -> None:
        _, data = self.check("\n## Workflow\n\n1. Survey.\n2. The audit runs after every write to each page.\n"
                             "\n## Signals\n\n- `In this tutorial, we will` opens the lesson.\n" + DIRECTIVE_TAIL)
        findings = [(f["rule"], f["line"]) for f in data["files"][0]["findings"]]
        self.assertEqual(sorted(findings), [("dir-verb", 6), ("dir-word-count", 5)])


class Evals(unittest.TestCase):
    def test_evals_schema(self) -> None:
        data = json.loads((SKILL / "evals" / "evals.json").read_text(encoding="utf-8"))
        self.assertEqual(data["skill_name"], "diataxis")
        self.assertEqual(len(data["evals"]), 3)
        for item in data["evals"]:
            self.assertTrue({"id", "prompt", "expected_output", "files"} <= set(item), item)


if __name__ == "__main__":
    unittest.main()
