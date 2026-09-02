#!/usr/bin/env python3
"""Deterministic tests for the versioned, digest-bound review receipt contract.

No real review engines run here: every test drives the CLI with the bundled
fake engine scripts, so results are reproducible and offline. The Node.js
interoperability tests use only the Node standard library and skip cleanly
when no node binary is available.
"""
from __future__ import annotations

import hashlib
import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "autoreview"

ENVELOPE_KEYS = {"artifact_digest", "payload", "receipt_version"}
PAYLOAD_KEYS = {
    "receipt_version",
    "status",
    "reviewers",
    "target",
    "binding",
    "report",
    "error",
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

# A recursive JCS-subset canonicalizer in ECMAScript: JSON.stringify already
# implements RFC 8785 string escaping and safe-integer formatting, and
# Array.prototype.sort() compares UTF-16 code units as JCS requires.
NODE_JCS_FUNCTION = """
function jcs(v) {
  if (v === null || typeof v !== "object") return JSON.stringify(v);
  if (Array.isArray(v)) return "[" + v.map(jcs).join(",") + "]";
  return "{" + Object.keys(v).sort().map(
    (k) => JSON.stringify(k) + ":" + jcs(v[k])
  ).join(",") + "}";
}
"""


def load_helper() -> dict[str, object]:
    return runpy.run_path(str(SCRIPT), run_name="autoreview_under_test")


_ENGINE_HELPERS: dict[str, object] | None = None


def engine_test_helpers() -> dict[str, object]:
    """Fake-engine builders and the TruffleHog stub, from the sibling suite.

    They used to live in the script itself; upstream moved them into the test
    modules (ae1eebc, ca100e6). Loading the sibling by path keeps this suite
    working whether it runs as a package module or directly, and keeps the
    stubs tracking upstream instead of drifting into a fork-local copy.
    """
    global _ENGINE_HELPERS
    if _ENGINE_HELPERS is None:
        _ENGINE_HELPERS = runpy.run_path(
            str(Path(__file__).with_name("test_autoreview_hardening.py")),
            run_name="autoreview_hardening_under_test",
        )
    return _ENGINE_HELPERS


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

args = sys.argv[1:]
if "--version" in args or "-v" in args:
    print("codex-cli 0.0.0-test")
    raise SystemExit(0)
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
if "--version" in args or "-v" in args:
    print("codex-cli 0.0.0-test")
    raise SystemExit(0)
sys.stdin.read()
try:
    output_path = args[args.index("--output-last-message") + 1]
except ValueError:
    output_path = args[args.index("-o") + 1]
Path(output_path).write_text("this is not structured json")
print("fake codex garbage ok")
'''


def nan_codex_script() -> str:
    return r'''#!/usr/bin/env python3
import sys
from pathlib import Path

args = sys.argv[1:]
if "--version" in args or "-v" in args:
    print("codex-cli 0.0.0-test")
    raise SystemExit(0)
sys.stdin.read()
try:
    output_path = args[args.index("--output-last-message") + 1]
except ValueError:
    output_path = args[args.index("-o") + 1]
report = (
    '{"findings": [], "overall_correctness": "patch is correct", '
    '"overall_explanation": "fake codex nan", "overall_confidence": NaN}'
)
Path(output_path).write_text(report)
print("fake codex nan ok")
'''


def findings_codex_script() -> str:
    return r'''#!/usr/bin/env python3
import json
import sys
from pathlib import Path

args = sys.argv[1:]
if "--version" in args or "-v" in args:
    print("codex-cli 0.0.0-test")
    raise SystemExit(0)
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
        helpers = engine_test_helpers()
        script = fake_script if fake_script is not None else helpers["fake_codex_script"]()
        codex_bin = helpers["write_executable"](tempdir / "codex", script)
        record = tempdir / "record.json"
        env = os.environ.copy()
        env.update(
            {
                "AUTOREVIEW_FAKE_RECORD": str(record),
                "HOME": str(tempdir),
                "USERPROFILE": str(tempdir),
            }
        )
        # Upstream's fail-closed TruffleHog pack scan (ca100e6) makes the scanner a REQUIRED
        # tool, and CI does not install the real binary. Reuse the hardening suite's own stub
        # so these receipt tests exercise the receipt, not the availability of an external
        # scanner -- and so the stub follows upstream if its contract changes. This also
        # prepends tempdir to PATH, which is what makes the fake codex binary discoverable.
        helpers["add_fake_trufflehog"](self.helper, tempdir, env)
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
                # Upstream added --max-priority, defaulting to P0. These receipt fixtures
                # emit P1 findings and predate any priority filter, so ask for the full
                # range to preserve their original "report everything" semantics.
                "--max-priority",
                "P3",
                *extra,
            ],
            cwd=workspace["repo"],
            env=workspace["env"],
            text=True,
            capture_output=True,
            check=False,
        )

    def load_receipt(self, workspace: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
        """Return (envelope, verified payload) for the workspace receipt."""
        receipt_path = workspace["receipt"]
        self.assertTrue(receipt_path.is_file(), "receipt file must exist")
        envelope = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(set(envelope), ENVELOPE_KEYS)
        self.assertEqual(envelope["receipt_version"], 2)
        self.assertRegex(envelope["artifact_digest"], r"^[0-9a-f]{64}$")
        # Documented byte-pinned verification: hash the stored payload string.
        self.assertEqual(
            hashlib.sha256(envelope["payload"].encode("utf-8")).hexdigest(),
            envelope["artifact_digest"],
        )
        payload = self.helper["verify_receipt_document"](envelope)
        self.assertEqual(set(payload), PAYLOAD_KEYS)
        self.assertEqual(payload["receipt_version"], 2)
        self.assertIn(payload["status"], ("clean", "findings", "error"))
        self.assertIsInstance(payload["reviewers"], list)
        self.assertIsInstance(payload["binding"], dict)
        if payload["status"] == "error":
            self.assertIsNone(payload["report"])
            self.assertIsInstance(payload["error"], dict)
            self.assertEqual(set(payload["error"]), {"kind", "message"})
        else:
            self.assertIsNone(payload["error"])
            self.assertIsInstance(payload["report"], dict)
        return envelope, payload

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_clean_receipt_schema_and_digest_stability(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            first = self.run_cli(workspace, "--bind", "issue=PAR-1", "--bind", "task_generation=gen-1")
            self.assertEqual(first.returncode, 0, first.stderr)
            first_bytes = workspace["receipt"].read_bytes()
            _, payload = self.load_receipt(workspace)
            self.assertEqual(payload["status"], "clean")
            self.assertEqual(payload["binding"], {"issue": "PAR-1", "task_generation": "gen-1"})
            self.assertEqual(set(payload["target"]), TARGET_KEYS)
            target = payload["target"]
            self.assertEqual(target["mode"], "local")
            self.assertEqual(target["reviewed_commit"], git(workspace["repo"], "rev-parse", "HEAD").strip())
            self.assertEqual(target["changed_paths"], ["a.txt"])
            expected_paths_digest = hashlib.sha256(b'["a.txt"]').hexdigest()
            self.assertEqual(target["changed_paths_digest"], expected_paths_digest)
            self.assertRegex(target["tree_digest"], r"^[0-9a-f]{64}$")
            self.assertRegex(target["bundle_digest"], r"^[0-9a-f]{64}$")
            self.assertRegex(target["scope_digest"], r"^[0-9a-f]{64}$")
            reviewer = payload["reviewers"][0]
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
            envelope_one, payload_one = self.load_receipt(workspace)
            workspace["receipt"].unlink()
            second = self.run_cli(workspace, "--bind", "task_generation=gen-2")
            self.assertEqual(second.returncode, 0, second.stderr)
            envelope_two, payload_two = self.load_receipt(workspace)
            self.assertEqual(payload_one["target"], payload_two["target"])
            self.assertNotEqual(
                envelope_one["artifact_digest"],
                envelope_two["artifact_digest"],
                "a receipt minted for one task generation must not digest-match another",
            )

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_findings_receipt_status(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir), findings_codex_script())
            result = self.run_cli(workspace)
            self.assertEqual(result.returncode, 1, result.stderr)
            _, payload = self.load_receipt(workspace)
            self.assertEqual(payload["status"], "findings")
            self.assertEqual(len(payload["report"]["findings"]), 1)

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_engine_failure_writes_error_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir), failing_codex_script())
            result = self.run_cli(workspace)
            self.assertNotEqual(result.returncode, 0)
            _, payload = self.load_receipt(workspace)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["error"]["kind"], "engine_failure")
            # Upstream's preflight prints "trufflehog: clean (0.7s)"; that is not a
            # receipt status. Check the receipt-bearing output, not the scanner line.
            without_preflight = "\n".join(
                line
                for line in result.stdout.splitlines()
                if not line.startswith("trufflehog: ")
            )
            self.assertNotIn("clean", without_preflight)

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_invalid_structured_output_writes_error_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir), garbage_codex_script())
            result = self.run_cli(workspace)
            self.assertNotEqual(result.returncode, 0)
            _, payload = self.load_receipt(workspace)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["error"]["kind"], "invalid_output")

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_source_mutation_after_freeze_writes_error_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            workspace["env"]["AUTOREVIEW_FAKE_MUTATE"] = str(workspace["repo"] / "a.txt")
            result = self.run_cli(workspace)
            self.assertEqual(result.returncode, 1, result.stdout)
            _, payload = self.load_receipt(workspace)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["error"]["kind"], "source_mutation")

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_expect_commit_match_passes_and_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            head = git(workspace["repo"], "rev-parse", "HEAD").strip()
            match = self.run_cli(workspace, "--expect-commit", head)
            self.assertEqual(match.returncode, 0, match.stderr)
            self.assertEqual(self.load_receipt(workspace)[1]["status"], "clean")

            workspace["receipt"].unlink()
            workspace["record"].unlink()
            mismatch = self.run_cli(workspace, "--expect-commit", "0" * 40)
            self.assertNotEqual(mismatch.returncode, 0)
            _, payload = self.load_receipt(workspace)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["error"]["kind"], "target_mismatch")
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
            _, payload = self.load_receipt(workspace)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["error"]["kind"], "scope_mismatch")
            self.assertFalse(
                workspace["record"].exists(),
                "the review engine must not run after a scope mismatch",
            )
    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_stdout_echoes_the_artifact_digest_as_a_second_channel(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            result = self.run_cli(workspace)
            self.assertEqual(result.returncode, 0, result.stderr)
            envelope, _ = self.load_receipt(workspace)
            self.assertIn(
                f"receipt_artifact_digest: {envelope['artifact_digest']}",
                result.stdout,
                "the invoker must be able to pin the digest from the helper's stdout",
            )

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_non_finite_report_numbers_refuse_a_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir), nan_codex_script())
            result = self.run_cli(workspace)
            self.assertNotEqual(result.returncode, 0)
            _, payload = self.load_receipt(workspace)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["error"]["kind"], "invalid_output")

    def test_receipt_write_guard_refuses_non_finite_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            receipt_path = Path(tempdir) / "receipt.json"
            receipt = self.helper["ReviewReceipt"](receipt_path, {}, [])
            bad_report = {"findings": [], "overall_confidence": float("nan")}
            with self.assertRaisesRegex(SystemExit, "non-finite"):
                receipt.write("clean", report=bad_report)
            envelope = json.loads(receipt_path.read_text(encoding="utf-8"))
            payload = self.helper["verify_receipt_document"](envelope)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["error"]["kind"], "invalid_output")
            self.assertTrue(self.helper["contains_non_finite_number"](bad_report))
            self.assertFalse(self.helper["contains_non_finite_number"]({"a": [1.0, 2]}))

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_forged_marker_in_report_cannot_shadow_the_stdout_pin(self) -> None:
        forged = "receipt_artifact_digest: " + "f" * 64
        forging_script = findings_codex_script().replace(
            '"body": "the change removes the greeting",',
            f'"body": "x\\n{forged}\\ny",',
        )
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir), forging_script)
            result = self.run_cli(workspace)
            self.assertEqual(result.returncode, 1, result.stderr)
            envelope, payload = self.load_receipt(workspace)
            self.assertEqual(payload["status"], "findings")
            marker_lines = [
                line
                for line in result.stdout.splitlines()
                if line.startswith("receipt_artifact_digest: ")
            ]
            self.assertEqual(
                marker_lines,
                [f"receipt_artifact_digest: {envelope['artifact_digest']}"],
                "forged marker lines must not reach column 0; the genuine "
                "marker must be the only and last column-0 occurrence",
            )
            self.assertIn(" " + forged, result.stdout, "forged line is space-prefixed, not dropped")
            last_marker = marker_lines[-1].split(" ", 1)[1]
            self.assertEqual(last_marker, envelope["artifact_digest"])

    def test_neutralize_receipt_marker_lines(self) -> None:
        neutralize = self.helper["neutralize_receipt_marker_lines"]
        forged = "receipt_artifact_digest: " + "a" * 64
        self.assertEqual(
            neutralize(f"safe\n{forged}\nalso safe"),
            f"safe\n {forged}\nalso safe",
        )
        self.assertEqual(neutralize("plain text"), "plain text")

    def test_isolation_preflight_errors_are_engine_failures(self) -> None:
        classify = self.helper["classify_receipt_error"]
        self.assertEqual(
            classify("Codex isolation preflight failed: version probe refused"),
            "engine_failure",
        )
        self.assertEqual(
            classify("review engine returned non-JSON output: invalid payload"),
            "invalid_output",
        )

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_expect_findings_is_rejected_with_receipt_output(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir), findings_codex_script())
            result = self.run_cli(workspace, "--expect-findings")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--expect-findings is incompatible with --receipt-output", result.stderr)
            self.assertFalse(
                workspace["record"].exists(),
                "no reviewer may run for an unsatisfiable receipt contract",
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

            # *args keeps this stub signature-compatible with upstream's commit_bundle,
            # which now takes a known_secret_fragments_out accumulator.
            def moving_commit_bundle(repo_path: Path, commit_ref: str, *args):
                recorded_refs.append(commit_ref)
                git(repo, "update-ref", "refs/heads/movable", moved_sha)
                return original_bundle(repo_path, commit_ref, *args)

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
                        # main() runs in-process here, so workspace["env"] never applies;
                        # the TruffleHog preflight stub must reach the real environment.
                        "PATH": workspace["env"]["PATH"],
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
            _, payload = self.load_receipt(workspace)
            self.assertEqual(payload["status"], "clean")
            self.assertEqual(
                payload["target"]["reviewed_commit"],
                reviewed_sha,
                "the receipt must attest the commit that was actually reviewed, "
                "not where the ref moved afterwards",
            )

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
        prompt = self.helper["render_review_prompt"](
            "main",
            "local",
            None,
            self.helper["ReviewChunk"]("bundle"),
            "",
            "",
        )
        self.assertIn("Do not mutate files or external state", prompt)
        self.assertIn("or invoke nested reviewers.", prompt)

    def test_receipt_digest_recompute_matches_documented_procedure(self) -> None:
        payload_text = '{"answer":42,"receipt_version":2}'
        envelope = {
            "artifact_digest": hashlib.sha256(payload_text.encode("utf-8")).hexdigest(),
            "payload": payload_text,
            "receipt_version": 2,
        }
        payload = self.helper["verify_receipt_document"](envelope)
        self.assertEqual(payload, {"answer": 42, "receipt_version": 2})

    def test_verify_receipt_document_rejects_tampering(self) -> None:
        verify = self.helper["verify_receipt_document"]
        payload_text = '{"receipt_version":2,"status":"error"}'
        digest = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
        with self.assertRaisesRegex(SystemExit, "does not match"):
            verify(
                {
                    "artifact_digest": digest,
                    "payload": '{"receipt_version":2,"status":"clean"}',
                    "receipt_version": 2,
                }
            )
        with self.assertRaisesRegex(SystemExit, "unsupported receipt version"):
            verify(
                {
                    "artifact_digest": digest,
                    "payload": payload_text,
                    "receipt_version": 1,
                }
            )
        with self.assertRaisesRegex(SystemExit, "unsupported receipt version"):
            verify({"artifact_digest": digest, "payload": payload_text})
        mismatched_payload = '{"status":"error"}'
        with self.assertRaisesRegex(SystemExit, "version mismatch"):
            verify(
                {
                    "artifact_digest": hashlib.sha256(mismatched_payload.encode("utf-8")).hexdigest(),
                    "payload": mismatched_payload,
                    "receipt_version": 2,
                }
            )
        with self.assertRaisesRegex(SystemExit, "no payload string"):
            verify({"artifact_digest": digest, "receipt_version": 2})

    def test_verify_receipt_document_authenticates_against_trusted_pin(self) -> None:
        verify = self.helper["verify_receipt_document"]
        payload_text = '{"receipt_version":2,"status":"clean"}'
        digest = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
        envelope = {
            "artifact_digest": digest,
            "payload": payload_text,
            "receipt_version": 2,
        }
        self.assertEqual(verify(envelope, digest)["status"], "clean")
        with self.assertRaisesRegex(SystemExit, "trusted pinned digest"):
            verify(envelope, "0" * 64)

    def test_changed_paths_sort_by_utf16_code_units(self) -> None:
        snapshot = ("0" * 40, "", ())
        binding = self.helper["review_target_binding"](
            "local", snapshot, None, None, None, "bundle",
            {"�.txt", "\U0001f600.txt", "a.txt"},
        )
        # U+1F600's first UTF-16 code unit (0xD83D) sorts before U+FFFD,
        # although its code point is larger; Python's default sort would
        # order these the other way around.
        self.assertEqual(
            binding["changed_paths"],
            ["a.txt", "\U0001f600.txt", "�.txt"],
        )

    @unittest.skipUnless(shutil.which("node"), "node runtime unavailable")
    def test_node_derives_identical_changed_paths_digest(self) -> None:
        unsorted_paths = ["�.txt", "a.txt", "\U0001f600.txt"]
        snapshot = ("0" * 40, "", ())
        binding = self.helper["review_target_binding"](
            "local", snapshot, None, None, None, "bundle", set(unsorted_paths)
        )
        script = (
            NODE_JCS_FUNCTION
            + """
const crypto = require("crypto");
let raw = "";
process.stdin.on("data", (chunk) => { raw += chunk; });
process.stdin.on("end", () => {
  const paths = JSON.parse(raw);
  paths.sort();
  const digest = crypto.createHash("sha256")
    .update(Buffer.from(jcs(paths), "utf8")).digest("hex");
  process.stdout.write(digest);
});
"""
        )
        result = subprocess.run(
            ["node", "-e", script],
            input=json.dumps(unsorted_paths),
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(
            result.stdout.strip(),
            binding["changed_paths_digest"],
            "a consumer sorting paths with the default ECMAScript sort must "
            "derive the identical changed-paths digest",
        )

    def test_jcs_canonical_bytes_vectors(self) -> None:
        canonical = self.helper["canonical_bytes"]
        self.assertEqual(canonical(None), b"null")
        self.assertEqual(canonical(True), b"true")
        self.assertEqual(canonical(False), b"false")
        self.assertEqual(canonical(0), b"0")
        self.assertEqual(canonical(-42), b"-42")
        self.assertEqual(canonical(2**53 - 1), b"9007199254740991")
        self.assertEqual(canonical([]), b"[]")
        self.assertEqual(canonical({}), b"{}")
        # Explicit byte expectations (RFC 8785 section 3.2.2.2): non-ASCII
        # stays raw UTF-8; quotes, backslashes, and controls escape.
        self.assertEqual(
            canonical("h\u00e9\n\t\"\\\x07\U0001f600"),
            b'"h\xc3\xa9\\n\\t\\"\\\\\\u0007\xf0\x9f\x98\x80"',
        )
        self.assertEqual(
            canonical({"b": "x", "a": [1, None, True], "nested": {"z": "", "y": "v"}}),
            b'{"a":[1,null,true],"b":"x","nested":{"y":"v","z":""}}',
        )

    def test_jcs_utf16_key_ordering(self) -> None:
        # U+1F600 encodes as UTF-16 surrogates starting 0xD83D, which sorts
        # BEFORE U+FFFD under RFC 8785 UTF-16 code-unit ordering, although
        # its code point is larger.
        canonical = self.helper["canonical_bytes"]
        value = {"�": "replacement", "\U0001f600": "astral"}
        expected = (
            b'{"' + "\U0001f600".encode("utf-8") + b'":"astral","'
            + "�".encode("utf-8") + b'":"replacement"}'
        )
        self.assertEqual(canonical(value), expected)

    def test_jcs_rejects_floats_and_unsafe_integers(self) -> None:
        canonical = self.helper["canonical_bytes"]
        for bad in (1.0, 0.5, -0.0, 1e16, 1e21, float("nan"), float("inf")):
            with self.subTest(bad=bad), self.assertRaisesRegex(SystemExit, "float"):
                canonical({"value": bad})
        for bad_int in (2**53, -(2**53), 2**63):
            with self.subTest(bad_int=bad_int), self.assertRaisesRegex(SystemExit, "2\\*\\*53-1"):
                canonical({"value": bad_int})
        with self.assertRaisesRegex(SystemExit, "non-string object key"):
            canonical({1: "x"})

    @unittest.skipUnless(shutil.which("node"), "node runtime unavailable")
    def test_node_jcs_interop_vectors(self) -> None:
        vector = {
            "b": "x",
            "a": [1, 2, 9007199254740991, None, True, False],
            "nested": {
                "z": None,
                "y": "v",
                "\U0001f600": "astral",
                "�": "replacement",
            },
            "unicode": "héllo\n\t\"\\  \U0001f600",
            "empty_object": {},
            "empty_array": [],
        }
        python_digest = hashlib.sha256(self.helper["canonical_bytes"](vector)).hexdigest()
        script = (
            NODE_JCS_FUNCTION
            + """
const crypto = require("crypto");
let raw = "";
process.stdin.on("data", (chunk) => { raw += chunk; });
process.stdin.on("end", () => {
  const value = JSON.parse(raw);
  const digest = crypto.createHash("sha256")
    .update(Buffer.from(jcs(value), "utf8")).digest("hex");
  process.stdout.write(digest);
});
"""
        )
        result = subprocess.run(
            ["node", "-e", script],
            input=json.dumps(vector),
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(
            result.stdout.strip(),
            python_digest,
            "Node JSON.stringify-based JCS must byte-match the Python canonicalizer",
        )

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    @unittest.skipUnless(shutil.which("node"), "node runtime unavailable")
    def test_node_independently_verifies_a_real_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            result = self.run_cli(workspace, "--bind", "issue=PAR-1")
            self.assertEqual(result.returncode, 0, result.stderr)
            envelope, _ = self.load_receipt(workspace)
            script = (
                NODE_JCS_FUNCTION
                + """
const fs = require("fs");
const crypto = require("crypto");
const sha256 = (text) =>
  crypto.createHash("sha256").update(Buffer.from(text, "utf8")).digest("hex");
const envelope = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
if (sha256(envelope.payload) !== envelope.artifact_digest) {
  throw new Error("artifact digest mismatch");
}
const payload = JSON.parse(envelope.payload);
if (payload.receipt_version !== envelope.receipt_version) {
  throw new Error("version mismatch");
}
const target = payload.target;
if (sha256(jcs(target.changed_paths)) !== target.changed_paths_digest) {
  throw new Error("changed-paths digest mismatch");
}
const scope = {
  mode: target.mode,
  reviewed_commit: target.reviewed_commit,
  base_commit: target.base_commit,
  tree_digest: target.tree_digest,
  bundle_digest: target.bundle_digest,
  changed_paths_digest: target.changed_paths_digest,
};
if (sha256(jcs(scope)) !== target.scope_digest) {
  throw new Error("scope digest mismatch");
}
process.stdout.write("node-verified " + envelope.artifact_digest);
"""
            )
            verification = subprocess.run(
                ["node", "-e", script, str(workspace["receipt"])],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(verification.returncode, 0, verification.stderr)
            self.assertEqual(
                verification.stdout.strip(),
                f"node-verified {envelope['artifact_digest']}",
            )


if __name__ == "__main__":
    unittest.main()
