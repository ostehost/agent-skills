#!/usr/bin/env python3
"""Deterministic tests for the versioned, digest-bound review receipt contract.

No real review engines run here: every test drives the CLI with the bundled
fake engine scripts, so results are reproducible and offline.
"""
from __future__ import annotations

import hashlib
import json
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "autoreview"

RECEIPT_KEYS = {
    "receipt_version",
    "status",
    "reviewers",
    "target",
    "binding",
    "report",
    "error",
    "artifact_digest",
}
TARGET_KEYS = {
    "mode",
    "reviewed_commit",
    "base_ref",
    "base_commit",
    "tree_digest",
    "bundle_digest",
    "changed_paths",
    "changed_paths_digest",
    "scope_digest",
}


def load_helper() -> dict[str, object]:
    return runpy.run_path(str(SCRIPT), run_name="autoreview_under_test")


def git(repo: Path, *args: str) -> str:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Receipt Test",
            "GIT_AUTHOR_EMAIL": "receipt@example.invalid",
            "GIT_COMMITTER_NAME": "Receipt Test",
            "GIT_COMMITTER_EMAIL": "receipt@example.invalid",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
    )
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def init_repo(tempdir: Path) -> Path:
    repo = tempdir / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Receipt Test")
    git(repo, "config", "user.email", "receipt@example.invalid")
    return repo


def failing_codex_script() -> str:
    return r'''#!/usr/bin/env python3
import os
import sys
from pathlib import Path

record = os.environ.get("AUTOREVIEW_FAKE_RECORD")
if record:
    Path(record).write_text("invoked")
print("simulated auth/transport failure", file=sys.stderr)
raise SystemExit(2)
'''


def garbage_codex_script() -> str:
    return r'''#!/usr/bin/env python3
import os
import sys
from pathlib import Path

args = sys.argv[1:]
sys.stdin.read()
try:
    output_path = args[args.index("--output-last-message") + 1]
except ValueError:
    output_path = args[args.index("-o") + 1]
Path(output_path).write_text("this is not structured json")
print("fake codex garbage ok")
'''


def findings_codex_script() -> str:
    return r'''#!/usr/bin/env python3
import json
import sys
from pathlib import Path

args = sys.argv[1:]
sys.stdin.read()
try:
    output_path = args[args.index("--output-last-message") + 1]
except ValueError:
    output_path = args[args.index("-o") + 1]
report = {
    "findings": [
        {
            "title": "deterministic test finding",
            "body": "the change removes the greeting",
            "priority": "P1",
            "confidence": 0.9,
            "category": "bug",
            "code_location": {"file_path": "a.txt", "line": 1},
        }
    ],
    "overall_correctness": "patch is incorrect",
    "overall_explanation": "fake codex found a defect",
    "overall_confidence": 0.9,
}
Path(output_path).write_text(json.dumps(report))
print("fake codex findings ok")
'''


class ReceiptContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.helper = load_helper()

    def make_workspace(self, tempdir: Path, fake_script: str | None = None) -> dict[str, object]:
        repo = init_repo(tempdir)
        (repo / "a.txt").write_text("hello\n", encoding="utf-8")
        git(repo, "add", "a.txt")
        git(repo, "commit", "-qm", "base")
        (repo / "a.txt").write_text("hello world\n", encoding="utf-8")
        script = fake_script if fake_script is not None else self.helper["fake_codex_script"]()
        codex_bin = self.helper["write_executable"](tempdir / "codex", script)
        record = tempdir / "record.json"
        env = os.environ.copy()
        env.update(
            {
                "AUTOREVIEW_FAKE_RECORD": str(record),
                "HOME": str(tempdir),
                "USERPROFILE": str(tempdir),
            }
        )
        return {
            "repo": repo,
            "codex_bin": codex_bin,
            "record": record,
            "env": env,
            "receipt": tempdir / "receipt.json",
        }

    def run_cli(self, workspace: dict[str, object], *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--mode",
                "local",
                "--engine",
                "codex",
                "--codex-bin",
                str(workspace["codex_bin"]),
                "--receipt-output",
                str(workspace["receipt"]),
                *extra,
            ],
            cwd=workspace["repo"],
            env=workspace["env"],
            text=True,
            capture_output=True,
            check=False,
        )

    def load_receipt(self, workspace: dict[str, object]) -> dict[str, object]:
        receipt_path = workspace["receipt"]
        self.assertTrue(receipt_path.is_file(), "receipt file must exist")
        document = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(set(document), RECEIPT_KEYS)
        self.assertEqual(document["receipt_version"], 1)
        self.assertIn(document["status"], ("clean", "findings", "error"))
        self.assertIsInstance(document["reviewers"], list)
        self.assertIsInstance(document["binding"], dict)
        self.assertRegex(document["artifact_digest"], r"^[0-9a-f]{64}$")
        recomputed = self.helper["receipt_artifact_digest"](document)
        self.assertEqual(recomputed, document["artifact_digest"])
        if document["status"] == "error":
            self.assertIsNone(document["report"])
            self.assertIsInstance(document["error"], dict)
            self.assertEqual(set(document["error"]), {"kind", "message"})
        else:
            self.assertIsNone(document["error"])
            self.assertIsInstance(document["report"], dict)
        return document

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_clean_receipt_schema_and_digest_stability(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            first = self.run_cli(workspace, "--bind", "issue=PAR-1", "--bind", "task_generation=gen-1")
            self.assertEqual(first.returncode, 0, first.stderr)
            first_bytes = workspace["receipt"].read_bytes()
            document = self.load_receipt(workspace)
            self.assertEqual(document["status"], "clean")
            self.assertEqual(document["binding"], {"issue": "PAR-1", "task_generation": "gen-1"})
            self.assertEqual(set(document["target"]), TARGET_KEYS)
            target = document["target"]
            self.assertEqual(target["mode"], "local")
            self.assertEqual(target["reviewed_commit"], git(workspace["repo"], "rev-parse", "HEAD").strip())
            self.assertEqual(target["changed_paths"], ["a.txt"])
            expected_paths_digest = hashlib.sha256(b'["a.txt"]').hexdigest()
            self.assertEqual(target["changed_paths_digest"], expected_paths_digest)
            self.assertRegex(target["tree_digest"], r"^[0-9a-f]{64}$")
            self.assertRegex(target["bundle_digest"], r"^[0-9a-f]{64}$")
            self.assertRegex(target["scope_digest"], r"^[0-9a-f]{64}$")
            reviewer = document["reviewers"][0]
            self.assertEqual(reviewer["engine"], "codex")
            self.assertEqual(reviewer["model"], "gpt-5.6-sol")
            self.assertEqual(reviewer["model_used"], "gpt-5.6-sol")

            workspace["receipt"].unlink()
            second = self.run_cli(workspace, "--bind", "issue=PAR-1", "--bind", "task_generation=gen-1")
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(workspace["receipt"].read_bytes(), first_bytes)

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_binding_changes_artifact_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            first = self.run_cli(workspace, "--bind", "task_generation=gen-1")
            self.assertEqual(first.returncode, 0, first.stderr)
            generation_one = self.load_receipt(workspace)
            workspace["receipt"].unlink()
            second = self.run_cli(workspace, "--bind", "task_generation=gen-2")
            self.assertEqual(second.returncode, 0, second.stderr)
            generation_two = self.load_receipt(workspace)
            self.assertEqual(generation_one["target"], generation_two["target"])
            self.assertNotEqual(
                generation_one["artifact_digest"],
                generation_two["artifact_digest"],
                "a receipt minted for one task generation must not digest-match another",
            )

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_findings_receipt_status(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir), findings_codex_script())
            result = self.run_cli(workspace)
            self.assertEqual(result.returncode, 1, result.stderr)
            document = self.load_receipt(workspace)
            self.assertEqual(document["status"], "findings")
            self.assertEqual(len(document["report"]["findings"]), 1)

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_engine_failure_writes_error_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir), failing_codex_script())
            result = self.run_cli(workspace)
            self.assertNotEqual(result.returncode, 0)
            document = self.load_receipt(workspace)
            self.assertEqual(document["status"], "error")
            self.assertEqual(document["error"]["kind"], "engine_failure")
            self.assertNotIn("clean", result.stdout)

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_invalid_structured_output_writes_error_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir), garbage_codex_script())
            result = self.run_cli(workspace)
            self.assertNotEqual(result.returncode, 0)
            document = self.load_receipt(workspace)
            self.assertEqual(document["status"], "error")
            self.assertEqual(document["error"]["kind"], "invalid_output")

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_source_mutation_after_freeze_writes_error_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            workspace["env"]["AUTOREVIEW_FAKE_MUTATE"] = str(workspace["repo"] / "a.txt")
            result = self.run_cli(workspace)
            self.assertEqual(result.returncode, 1, result.stdout)
            document = self.load_receipt(workspace)
            self.assertEqual(document["status"], "error")
            self.assertEqual(document["error"]["kind"], "source_mutation")

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_expect_commit_match_passes_and_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            head = git(workspace["repo"], "rev-parse", "HEAD").strip()
            match = self.run_cli(workspace, "--expect-commit", head)
            self.assertEqual(match.returncode, 0, match.stderr)
            self.assertEqual(self.load_receipt(workspace)["status"], "clean")

            workspace["receipt"].unlink()
            workspace["record"].unlink()
            mismatch = self.run_cli(workspace, "--expect-commit", "0" * 40)
            self.assertNotEqual(mismatch.returncode, 0)
            document = self.load_receipt(workspace)
            self.assertEqual(document["status"], "error")
            self.assertEqual(document["error"]["kind"], "target_mismatch")
            self.assertFalse(
                workspace["record"].exists(),
                "the review engine must not run after a target mismatch",
            )

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_expect_changed_paths_digest_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            expected = hashlib.sha256(b'["a.txt"]').hexdigest()
            match = self.run_cli(workspace, "--expect-changed-paths-digest", expected)
            self.assertEqual(match.returncode, 0, match.stderr)

            workspace["receipt"].unlink()
            workspace["record"].unlink()
            mismatch = self.run_cli(workspace, "--expect-changed-paths-digest", "0" * 64)
            self.assertNotEqual(mismatch.returncode, 0)
            document = self.load_receipt(workspace)
            self.assertEqual(document["status"], "error")
            self.assertEqual(document["error"]["kind"], "scope_mismatch")
            self.assertFalse(
                workspace["record"].exists(),
                "the review engine must not run after a scope mismatch",
            )

    @unittest.skipIf(os.name == "nt", "the true/false commands are POSIX-only")
    def test_parallel_test_failure_is_never_a_clean_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            result = self.run_cli(workspace, "--parallel-tests", "false")
            self.assertEqual(result.returncode, 1, result.stderr)
            document = self.load_receipt(workspace)
            self.assertEqual(document["status"], "error")
            self.assertEqual(document["error"]["kind"], "parallel_tests_failed")

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_bind_requires_receipt_output(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--mode",
                    "local",
                    "--engine",
                    "codex",
                    "--codex-bin",
                    str(workspace["codex_bin"]),
                    "--bind",
                    "issue=PAR-1",
                ],
                cwd=workspace["repo"],
                env=workspace["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--bind requires --receipt-output", result.stderr)

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_receipt_output_inside_repo_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            workspace["receipt"] = workspace["repo"] / "receipt.json"
            result = self.run_cli(workspace)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--receipt-output must point outside the reviewed repository", result.stderr)
            self.assertFalse(workspace["receipt"].exists())

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_allow_partial_panel_is_rejected_with_receipt_output(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            result = self.run_cli(workspace, "--reviewers", "codex,claude", "--allow-partial-panel")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--allow-partial-panel is incompatible with --receipt-output", result.stderr)
            self.assertFalse(
                workspace["record"].exists(),
                "no reviewer may run when the receipt contract is unsatisfiable",
            )
            self.assertFalse(workspace["receipt"].exists())

    def test_changed_paths_digest_is_injective_for_newline_paths(self) -> None:
        snapshot = ("0" * 40, "", ())
        binding_one = self.helper["review_target_binding"](
            "local", snapshot, None, None, None, "bundle", {"a", "b"}
        )
        binding_two = self.helper["review_target_binding"](
            "local", snapshot, None, None, None, "bundle", {"a\nb"}
        )
        self.assertNotEqual(
            binding_one["changed_paths_digest"],
            binding_two["changed_paths_digest"],
            "paths [a, b] and [a\\nb] must not share a digest",
        )
        self.assertNotEqual(binding_one["scope_digest"], binding_two["scope_digest"])

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_movable_ref_is_frozen_before_bundle_construction(self) -> None:
        import contextlib
        import io
        from unittest import mock

        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            workspace = self.make_workspace(root)
            repo = workspace["repo"]
            git(repo, "add", "a.txt")
            git(repo, "commit", "-qm", "second")
            reviewed_sha = git(repo, "rev-parse", "HEAD").strip()
            (repo / "a.txt").write_text("third\n", encoding="utf-8")
            git(repo, "add", "a.txt")
            git(repo, "commit", "-qm", "third")
            moved_sha = git(repo, "rev-parse", "HEAD").strip()
            git(repo, "branch", "movable", reviewed_sha)

            original_bundle = self.helper["commit_bundle"]
            recorded_refs: list[str] = []

            def moving_commit_bundle(repo_path: Path, commit_ref: str):
                recorded_refs.append(commit_ref)
                git(repo, "update-ref", "refs/heads/movable", moved_sha)
                return original_bundle(repo_path, commit_ref)

            argv = [
                "autoreview",
                "--mode",
                "commit",
                "--commit",
                "movable",
                "--engine",
                "codex",
                "--codex-bin",
                str(workspace["codex_bin"]),
                "--receipt-output",
                str(workspace["receipt"]),
            ]
            cwd = os.getcwd()
            os.chdir(repo)
            try:
                with mock.patch.dict(
                    self.helper["main"].__globals__,
                    {"commit_bundle": moving_commit_bundle},
                ), mock.patch.object(sys, "argv", argv), mock.patch.dict(
                    os.environ,
                    {
                        "AUTOREVIEW_FAKE_RECORD": str(workspace["record"]),
                        "HOME": str(root),
                        "USERPROFILE": str(root),
                    },
                ), contextlib.redirect_stdout(io.StringIO()):
                    exit_code = self.helper["main"]()
            finally:
                os.chdir(cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                recorded_refs,
                [reviewed_sha],
                "the bundle must be built from the frozen sha, not the movable ref name",
            )
            document = self.load_receipt(workspace)
            self.assertEqual(document["status"], "clean")
            self.assertEqual(
                document["target"]["reviewed_commit"],
                reviewed_sha,
                "the receipt must attest the commit that was actually reviewed, "
                "not where the ref moved afterwards",
            )

    def test_binding_pair_validation(self) -> None:
        parse = self.helper["parse_binding_pairs"]
        self.assertEqual(parse(["a=1", "b.c-d_e=x"]), {"a": "1", "b.c-d_e": "x"})
        with self.assertRaisesRegex(SystemExit, "key=value"):
            parse(["novalue"])
        with self.assertRaisesRegex(SystemExit, "key must be"):
            parse(["bad key=1"])
        with self.assertRaisesRegex(SystemExit, "repeated"):
            parse(["a=1", "a=2"])
        with self.assertRaisesRegex(SystemExit, "exceeds"):
            parse(["a=" + "x" * 501])

    def test_prompt_bans_nested_reviewers(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            repo = init_repo(Path(tempdir))
            prompt = self.helper["build_prompt"](repo, "local", None, "bundle", "", "")
            self.assertIn("Do not invoke nested reviewers or review tools.", prompt)
            self.assertIn(
                "Forbidden nested review commands include: codex review, autoreview, claude review, oracle review.",
                prompt,
            )

    def test_receipt_digest_recompute_matches_documented_procedure(self) -> None:
        receipt = {
            "receipt_version": 1,
            "status": "clean",
            "reviewers": [],
            "target": None,
            "binding": {},
            "report": {"findings": []},
            "error": None,
        }
        digest = self.helper["receipt_artifact_digest"](receipt)
        unsigned = {**receipt, "artifact_digest": ""}
        expected = hashlib.sha256(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        ).hexdigest()
        self.assertEqual(digest, expected)
        signed = {**receipt, "artifact_digest": digest}
        self.assertEqual(self.helper["receipt_artifact_digest"](signed), digest)


if __name__ == "__main__":
    unittest.main()
