#!/usr/bin/env python3
"""Deterministic tests for the versioned, digest-bound review receipt contract.

No real review engines run here: every test drives the CLI with the bundled
fake engine scripts, so results are reproducible and offline. The Node.js
interoperability tests use only the Node standard library and skip cleanly
when no node binary is available.

Fork-only: this lives under fork-tests/ because upstream's manifest self-test
requires every skills/autoreview/tests/test_*.py to be in its TEST_MODULES.
It loads the checkout's autoreview and upstream's hardening helpers by path,
never through a skills.autoreview.tests package.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "autoreview" / "scripts" / "autoreview"
HARDENING = ROOT / "skills" / "autoreview" / "tests" / "test_autoreview_hardening.py"

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
REVIEWER_KEYS = {"engine", "model", "model_used", "fallback_model", "thinking"}
MARKER_PREFIX = "receipt_artifact_digest: "

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
    """Fake-engine builders, from upstream's hardening suite.

    They used to live in the script itself; upstream moved them into the test
    modules (ae1eebc, ca100e6). Loading that file by path keeps this suite
    independent of any package layout, and keeps the stubs tracking upstream
    instead of drifting into a fork-local copy.
    """
    global _ENGINE_HELPERS
    if _ENGINE_HELPERS is None:
        _ENGINE_HELPERS = runpy.run_path(
            str(HARDENING),
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
    '"overall_explanation": "fake codex nan", "overall_confidence": NaN, '
    '"review_completion": "complete"}'
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
    "review_completion": "complete",
}
Path(output_path).write_text(json.dumps(report))
print("fake codex findings ok")
'''


def report_codex_script(report: dict[str, object]) -> str:
    """A fake codex that answers every pass with exactly `report`."""
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
Path(output_path).write_text(json.dumps(REPORT_JSON))
print("fake codex report ok")
'''.replace("REPORT_JSON", repr(json.loads(json.dumps(report))))


def model_access_failure_codex_script(script: str, primary: str) -> str:
    """Upstream's fake codex, refusing `primary` with a model-access error."""
    failure = (
        'model = args[args.index("--model") + 1]\n'
        f'if model == {primary!r}:\n'
        '    print(json.dumps({"type": "error", "message": '
        'f"The model {model} does not exist or you do not have access to it."}))\n'
        '    raise SystemExit(17)\n'
    )
    marker = 'print("fake codex ok")'
    assert script.count(marker) == 1, "upstream fake_codex_script changed shape"
    return script.replace(marker, failure + marker)


# Upstream now rejects engine output without review_completion. A fixture that
# forgets it is refused for that reason alone, which would let an
# error-receipt test pass for the wrong cause.
UNRELATED_REJECTION = "review_completion"


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
        # A developer's AUTOREVIEW_* defaults (model, engine, priority) must not
        # leak into fixtures; upstream's CLI tests filter them the same way.
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("AUTOREVIEW_") or key == "AUTOREVIEW_GIT"}
        env.update(
            {
                "AUTOREVIEW_FAKE_RECORD": str(record),
                "HOME": str(tempdir),
                "USERPROFILE": str(tempdir),
                "CODEX_HOME": str(tempdir),
            }
        )
        # Upstream removed the TruffleHog preflight in #240 (intentional scanner-free
        # policy), so there is no scanner to stub. The fake codex binary still has to be
        # discoverable, which the stub used to arrange as a side effect of prepending
        # tempdir to PATH -- do that explicitly now.
        env["PATH"] = os.pathsep.join([str(tempdir), env.get("PATH", "")])
        return {
            "repo": repo,
            "codex_bin": codex_bin,
            "record": record,
            "env": env,
            "receipt": tempdir / "receipt.json",
        }

    def run_cli(self, workspace: dict[str, object], *extra: str,
                receipt: bool = True) -> subprocess.CompletedProcess[str]:
        receipt_args = ["--receipt-output", str(workspace["receipt"])] if receipt else []
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
                *receipt_args,
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

    def run_main(
        self,
        workspace: dict[str, object],
        argv: list[str],
        patches: dict[str, object] | None = None,
    ) -> tuple[int | None, BaseException | None, str, str]:
        """Drive the real main() in-process; return (exit, raised, stdout, stderr)."""
        stdout, stderr = io.StringIO(), io.StringIO()
        main = self.helper["main"]
        cwd = os.getcwd()
        os.chdir(workspace["repo"])
        try:
            with mock.patch.dict(main.__globals__, patches or {}), \
                    mock.patch.object(sys, "argv", ["autoreview", *argv]), \
                    mock.patch.dict(os.environ, workspace["env"], clear=True), \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                try:
                    return main(), None, stdout.getvalue(), stderr.getvalue()
                except SystemExit as exc:
                    return None, exc, stdout.getvalue(), stderr.getvalue()
        finally:
            os.chdir(cwd)

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
        for reviewer in payload["reviewers"]:
            self.assertEqual(set(reviewer), REVIEWER_KEYS)
        self.assertIsInstance(payload["binding"], dict)
        if payload["status"] == "error":
            self.assertIsNone(payload["report"])
            self.assertIsInstance(payload["error"], dict)
            self.assertEqual(set(payload["error"]), {"kind", "message"})
            self.assertNotIn(
                UNRELATED_REJECTION,
                payload["error"]["message"],
                "fixture was rejected for missing review_completion, not for the "
                "failure this test exercises",
            )
        else:
            self.assertIsNone(payload["error"])
            self.assertIsInstance(payload["report"], dict)
        return envelope, payload

    def assert_marker_is_last_line(self, stdout: str, workspace: dict[str, object]) -> None:
        """The genuine digest marker must be the final stdout line on success paths."""
        envelope = json.loads(workspace["receipt"].read_text(encoding="utf-8"))
        lines = stdout.rstrip("\n").splitlines()
        self.assertTrue(lines, "no stdout")
        self.assertEqual(lines[-1], f"{MARKER_PREFIX}{envelope['artifact_digest']}",
                         "the receipt digest marker must be the last stdout line")
        self.assertEqual(sum(line.startswith(MARKER_PREFIX) for line in lines), 1)

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
            default_model = self.helper["DEFAULT_MODEL_BY_ENGINE"]["codex"]
            self.assertEqual(reviewer["engine"], "codex")
            self.assertEqual(reviewer["model"], default_model)
            self.assertEqual(reviewer["model_used"], default_model)
            self.assert_marker_is_last_line(first.stdout, workspace)

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
            self.assert_marker_is_last_line(result.stdout, workspace)

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_engine_failure_writes_error_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir), failing_codex_script())
            result = self.run_cli(workspace)
            self.assertNotEqual(result.returncode, 0)
            _, payload = self.load_receipt(workspace)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["error"]["kind"], "engine_failure")
            self.assertNotIn("clean", result.stdout)

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
            exit_code, raised, _, stderr = self.run_main(
                workspace, argv, {"commit_bundle": moving_commit_bundle},
            )
            self.assertIsNone(raised, stderr)
            self.assertEqual(exit_code, 0, stderr)
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

    # -- 2026-11 sync: behaviours upstream's rewrite would otherwise drop ------

    def fallback_workspace(self, tempdir: Path) -> tuple[dict[str, object], str, str]:
        primary = self.helper["DEFAULT_MODEL_BY_ENGINE"]["codex"]
        fallback = self.helper["DEFAULT_CODEX_ACCESS_FALLBACK_MODEL"]
        self.assertNotEqual(primary, fallback)
        script = model_access_failure_codex_script(
            engine_test_helpers()["fake_codex_script"](), primary,
        )
        workspace = self.make_workspace(tempdir, script)
        workspace["env"]["AUTOREVIEW_FAKE_CODEX_INVOCATIONS"] = str(tempdir / "invocations.jsonl")
        return workspace, primary, fallback

    def invoked_models(self, workspace: dict[str, object]) -> list[str]:
        path = Path(workspace["env"]["AUTOREVIEW_FAKE_CODEX_INVOCATIONS"])
        attempts = [json.loads(line)["argv"] for line in path.read_text().splitlines()]
        return [argv[argv.index("--model") + 1] for argv in attempts if "exec" in argv]

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_model_used_attests_the_fallback_model_through_main(self) -> None:
        # Upstream's run_reviewer reviews on copy.copy(args), so the engine's
        # model_used lands on a throwaway namespace unless it is carried back.
        with tempfile.TemporaryDirectory() as tempdir:
            workspace, primary, fallback = self.fallback_workspace(Path(tempdir))
            argv = ["--mode", "local", "--engine", "codex",
                    "--codex-bin", str(workspace["codex_bin"]),
                    "--receipt-output", str(workspace["receipt"])]
            exit_code, raised, _, stderr = self.run_main(workspace, argv)
            self.assertIsNone(raised, stderr)
            self.assertEqual(exit_code, 0, stderr)
            self.assertEqual(self.invoked_models(workspace), [primary, fallback])
            _, payload = self.load_receipt(workspace)
            self.assertEqual(payload["status"], "clean")
            reviewer = payload["reviewers"][0]
            self.assertEqual(reviewer["model"], primary)
            self.assertEqual(reviewer["model_used"], fallback)

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_model_used_check_detects_a_removed_write_back(self) -> None:
        # Mutation proof for the test above: the same run against a copy of the
        # helper without the write-back must attest no model at all.
        write_back = "        reviewer.model_used = model_used\n"
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(source.count(write_back), 1, "write-back line moved; update the mutation")
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            mutant = root / "mutant" / "autoreview"
            mutant.parent.mkdir()
            mutant.write_text(source.replace(write_back, "        pass\n"), encoding="utf-8")
            workspace, primary, fallback = self.fallback_workspace(root)
            result = subprocess.run(
                [sys.executable, str(mutant), "--mode", "local", "--engine", "codex",
                 "--codex-bin", str(workspace["codex_bin"]),
                 "--receipt-output", str(workspace["receipt"])],
                cwd=workspace["repo"], env=workspace["env"],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(self.invoked_models(workspace), [primary, fallback])
            _, payload = self.load_receipt(workspace)
            self.assertIsNone(payload["reviewers"][0]["model_used"])

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_interrupt_writes_an_interrupted_error_receipt(self) -> None:
        interrupted = self.helper["EngineInterrupted"]

        def interrupting_engine(*_args, **_kwargs):
            raise interrupted(130)

        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            status = Path(tempdir) / "status.json"
            argv = ["--mode", "local", "--engine", "codex",
                    "--codex-bin", str(workspace["codex_bin"]),
                    "--receipt-output", str(workspace["receipt"]),
                    "--status-output", str(status)]
            exit_code, raised, stdout, stderr = self.run_main(
                workspace, argv, {"run_engine": interrupting_engine},
            )
            self.assertIsNone(raised, stderr)
            self.assertEqual(exit_code, 130)
            envelope, payload = self.load_receipt(workspace)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["error"]["kind"], "interrupted")
            self.assertIn("signal 2", payload["error"]["message"])
            self.assertEqual(json.loads(status.read_text())["status"], "interrupted")
            self.assertEqual(
                stdout.rstrip("\n").splitlines()[-1],
                f"receipt_artifact_digest: {envelope['artifact_digest']}",
            )

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_interrupt_keeps_its_exit_code_when_the_receipt_cannot_be_written(self) -> None:
        interrupted = self.helper["EngineInterrupted"]
        original_write = self.helper["main"].__globals__["atomic_write_text"]

        def interrupting_engine(*_args, **_kwargs):
            raise interrupted(143)

        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            receipt_path = workspace["receipt"]

            def failing_receipt_write(path, content):
                if Path(path).name == receipt_path.name:
                    raise OSError("simulated full disk")
                return original_write(path, content)

            argv = ["--mode", "local", "--engine", "codex",
                    "--codex-bin", str(workspace["codex_bin"]),
                    "--receipt-output", str(receipt_path)]
            exit_code, raised, _, stderr = self.run_main(
                workspace, argv,
                {"run_engine": interrupting_engine, "atomic_write_text": failing_receipt_write},
            )
            self.assertIsNone(raised, stderr)
            self.assertEqual(exit_code, 143, "the signal exit code must survive a failed receipt write")
            self.assertFalse(receipt_path.exists())
            self.assertIn("error receipt could not be written", stderr)

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_base_ref_moving_during_bundling_is_a_source_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            repo = workspace["repo"]
            base_sha = git(repo, "rev-parse", "HEAD").strip()
            git(repo, "branch", "movable", base_sha)
            git(repo, "add", "a.txt")
            git(repo, "commit", "-qm", "reviewed change")
            head_sha = git(repo, "rev-parse", "HEAD").strip()
            argv = ["--mode", "branch", "--base", "movable", "--engine", "codex",
                    "--codex-bin", str(workspace["codex_bin"]),
                    "--receipt-output", str(workspace["receipt"])]

            # Control: an unmoved base. D9 keeps the ref NAME in what the
            # reviewer sees and records the pinned SHA beside it.
            exit_code, raised, _, stderr = self.run_main(workspace, argv)
            self.assertIsNone(raised, stderr)
            self.assertEqual(exit_code, 0, stderr)
            _, payload = self.load_receipt(workspace)
            self.assertEqual(payload["status"], "clean")
            self.assertEqual(payload["target"]["mode"], "branch")
            self.assertEqual(payload["target"]["base_ref"], "movable")
            self.assertEqual(payload["target"]["base_commit"], base_sha)
            self.assertEqual(payload["target"]["reviewed_commit"], head_sha)
            prompt = json.loads(workspace["record"].read_text())["stdin"]
            self.assertIn("branch movable", prompt)
            self.assertNotIn(f"branch {base_sha}", prompt)

            workspace["receipt"].unlink()
            workspace["record"].unlink()
            original_bundle = self.helper["branch_bundle"]

            def moving_branch_bundle(repo_path, base_ref, *args, **kwargs):
                captured = original_bundle(repo_path, base_ref, *args, **kwargs)
                git(repo, "update-ref", "refs/heads/movable", head_sha)
                return captured

            exit_code, raised, _, stderr = self.run_main(
                workspace, argv, {"branch_bundle": moving_branch_bundle},
            )
            self.assertIsNone(exit_code)
            self.assertIsInstance(raised, SystemExit)
            self.assertIn("moved from", str(raised.code))
            _, payload = self.load_receipt(workspace)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["error"]["kind"], "source_mutation")
            self.assertFalse(
                workspace["record"].exists(),
                "the review engine must not run after the base ref moved",
            )

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_tree_changing_during_bundling_is_a_source_mutation(self) -> None:
        # Upstream owns this refusal and its wording; the receipt kind is derived
        # from that wording. Pin the kind here so an upstream reword turns this
        # gate red instead of silently degrading the receipt to helper_failure.
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            repo = workspace["repo"]
            base_sha = git(repo, "rev-parse", "HEAD").strip()
            git(repo, "branch", "movable", base_sha)
            git(repo, "add", "a.txt")
            git(repo, "commit", "-qm", "reviewed change")
            argv = ["--mode", "branch", "--base", "movable", "--engine", "codex",
                    "--codex-bin", str(workspace["codex_bin"]),
                    "--receipt-output", str(workspace["receipt"])]
            original_bundle = self.helper["branch_bundle"]

            def editing_branch_bundle(repo_path, base_ref, *args, **kwargs):
                captured = original_bundle(repo_path, base_ref, *args, **kwargs)
                with (repo / "a.txt").open("a", encoding="utf-8") as handle:
                    handle.write("edited while the bundle was being created\n")
                return captured

            exit_code, raised, _, stderr = self.run_main(
                workspace, argv, {"branch_bundle": editing_branch_bundle},
            )
            self.assertIsNone(exit_code, stderr)
            self.assertIsInstance(raised, SystemExit)
            _, payload = self.load_receipt(workspace)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["error"]["kind"], "source_mutation")
            self.assertFalse(
                workspace["record"].exists(),
                "the review engine must not run after the tree changed",
            )

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_stale_receipt_is_removed_at_the_start_of_a_run(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            first = self.run_cli(workspace)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(self.load_receipt(workspace)[1]["status"], "clean")
            # A later run that fails before any receipt is minted must not leave
            # the earlier clean receipt behind for a consumer to pick up.
            failed = self.run_cli(workspace, "--bind", "bad key=1")
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("--bind key must be", failed.stderr)
            self.assertFalse(workspace["receipt"].exists(), "stale clean receipt survived a failed run")

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_native_handoff_with_receipt_output_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            handoff = Path(tempdir) / "handoff"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--mode", "local", "--engine", "openclaw",
                 "--native-handoff", str(handoff),
                 "--receipt-output", str(workspace["receipt"]),
                 # Without the refusal, the helper would wait for a parent that
                 # never answers; bound it so a regression fails, not hangs.
                 "--engine-timeout-seconds", "5"],
                cwd=workspace["repo"], env=workspace["env"],
                text=True, capture_output=True, check=False, timeout=60,
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("--receipt-output cannot attest a --native-handoff review", result.stderr)
            self.assertFalse(handoff.exists())
            self.assertFalse(workspace["receipt"].exists())

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_receipt_output_must_differ_from_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            result = self.run_cli(workspace, "--json-output", str(workspace["receipt"]))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--receipt-output must use a different path from --json-output", result.stderr)
            self.assertFalse(workspace["record"].exists())

    def test_receipt_redacts_proxy_credentials_before_the_digest(self) -> None:
        secret = "pw-s3cret-1f71"
        proxy = f"http://alice:{secret}@proxy.invalid:8080"
        report = {
            "findings": [],
            "overall_correctness": "patch is correct",
            "overall_explanation": f"reviewer echoed {proxy} back",
            "overall_confidence": 1,
        }
        with tempfile.TemporaryDirectory() as tempdir, \
                mock.patch.dict(os.environ, {"HTTPS_PROXY": proxy}):
            path = Path(tempdir) / "receipt.json"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.helper["ReviewReceipt"](path, {}, []).write("clean", report=report)
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn(secret, raw)
            envelope = json.loads(raw)
            payload = self.helper["verify_receipt_document"](envelope)
            self.assertIn("[REDACTED]", payload["report"]["overall_explanation"])
            # The pinned digest covers the redacted bytes, not the original ones.
            self.assertEqual(stdout.getvalue().strip(),
                             f"receipt_artifact_digest: {envelope['artifact_digest']}")
            unredacted = dict(payload, report=report)
            self.assertNotEqual(
                envelope["artifact_digest"],
                self.helper["sha256_hex"](self.helper["canonical_json"](unredacted)),
            )
            self.assertIn(secret, report["overall_explanation"], "caller's report must not be mutated")

            error_path = Path(tempdir) / "error.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.helper["ReviewReceipt"](error_path, {}, []).write_error(
                    "engine_failure", f"proxy {proxy} refused",
                )
            self.assertNotIn(secret, error_path.read_text(encoding="utf-8"))

    def test_typed_failures_classify_before_message_text(self) -> None:
        classify = self.helper["classify_receipt_exception"]
        unavailable = self.helper["ReviewerUnavailable"]
        self.assertEqual(
            classify(unavailable("review engine returned missing or invalid review_completion",
                                 reason="invalid_report")),
            ("invalid_output", "review engine returned missing or invalid review_completion"),
        )
        self.assertEqual(classify(unavailable("codex engine failed (2)"))[0], "engine_failure")
        self.assertEqual(classify(self.helper["EngineInterrupted"](130))[0], "interrupted")
        self.assertEqual(classify(SystemExit("source changed after x"))[0], "source_mutation")
        self.assertEqual(classify(RuntimeError())[1], "RuntimeError")

    # -- repair round: gaps the adversarial mutation pass found ---------------

    def status_report(self, **overrides: object) -> dict[str, object]:
        report: dict[str, object] = {
            "findings": [],
            "overall_correctness": "patch is correct",
            "overall_explanation": "fake codex status fixture",
            "overall_confidence": 0.9,
            "review_completion": "complete",
        }
        report.update(overrides)
        return report

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_receipt_is_clean_only_for_a_scoped_clean_review(self) -> None:
        p1 = {
            "title": "low priority note",
            "body": "a P1 observation",
            "priority": "P1",
            "confidence": 0.9,
            "category": "bug",
            "code_location": {"file_path": "a.txt", "line": 1},
        }
        cases = [
            # (name, report, extra argv, expected review_status, expected exit)
            ("incomplete", self.status_report(review_completion="incomplete"), (), "incomplete", 2),
            ("incorrect", self.status_report(overall_correctness="patch is incorrect"), (), "incorrect", 1),
            ("filtered", self.status_report(findings=[p1]), ("--max-priority", "P0"), "filtered", 0),
        ]
        for name, report, extra, review_status, exit_code in cases:
            with self.subTest(name), tempfile.TemporaryDirectory() as tempdir:
                workspace = self.make_workspace(Path(tempdir), report_codex_script(report))
                result = self.run_cli(workspace, *extra)
                self.assertEqual(result.returncode, exit_code, result.stdout + result.stderr)
                _, payload = self.load_receipt(workspace)
                self.assertEqual(payload["report"]["review_status"], review_status)
                self.assertEqual(payload["status"], "findings",
                                 f"a {review_status} review must never mint a clean receipt")
                self.assert_marker_is_last_line(result.stdout, workspace)

    def test_every_report_print_site_neutralizes_forged_markers(self) -> None:
        def forged(tag: str) -> str:
            return f"{MARKER_PREFIX}{tag * 64}"

        finding = {
            "title": "t",
            "body": f"finding body\n{forged('a')}",
            "priority": "P1",
            "confidence": 0.5,
            "category": "bug",
            "code_location": {"file_path": "a.txt", "line": 1},
            "claim_variants": [{
                "body": f"variant body\n{forged('b')}",
                "observations": [{"pass": "p1", "priority": "P1", "title": "t", "confidence": 0.5}],
            }],
        }
        report = {
            "review_status": "findings",
            "findings": [finding],
            "overall_correctness": "patch is incorrect",
            "overall_confidence": 0.5,
            "overall_explanation": f"overall\n{forged('c')}",
            "pass_reports": [{
                "label": "pass 1",
                "report": {
                    "overall_correctness": "patch is incorrect",
                    "overall_confidence": 0.5,
                    "overall_explanation": f"pass\n{forged('d')}",
                },
            }],
        }
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.helper["print_report"](report, label="autoreview")
        lines = stdout.getvalue().splitlines()
        for site, tag in (("finding body", "a"), ("claim variant body", "b"),
                          ("overall explanation", "c"), ("pass report explanation", "d")):
            with self.subTest(site):
                self.assertIn(" " + forged(tag), lines, f"{site} line missing or not space-prefixed")
                self.assertNotIn(forged(tag), lines, f"{site} printed a forged marker at column 0")
        self.assertFalse([line for line in lines if line.startswith(MARKER_PREFIX)])

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_expect_flags_fail_closed_without_receipt_output(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            head = git(workspace["repo"], "rev-parse", "HEAD").strip()
            cases = [
                ("--expect-commit", "0" * 40, "does not match --expect-commit"),
                ("--expect-changed-paths-digest", "0" * 64, "does not match --expect-changed-paths-digest"),
            ]
            for flag, value, needle in cases:
                with self.subTest(flag):
                    workspace["record"].unlink(missing_ok=True)
                    result = self.run_cli(workspace, flag, value, receipt=False)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn(needle, result.stderr)
                    self.assertFalse(workspace["record"].exists(),
                                     f"{flag} must be enforced before any engine runs, receipt or not")
                    self.assertFalse(workspace["receipt"].exists())
            # Control: a matching expectation without a receipt reviews normally.
            match = self.run_cli(workspace, "--expect-commit", head, receipt=False)
            self.assertEqual(match.returncode, 0, match.stderr)
            self.assertTrue(workspace["record"].exists())

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_receipt_output_alias_through_a_symlink_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            alias = Path(tempdir) / "report-alias.json"
            alias.symlink_to(workspace["receipt"])
            result = self.run_cli(workspace, "--json-output", str(alias))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--receipt-output must use a different path from --json-output", result.stderr)
            self.assertFalse(workspace["record"].exists())
            self.assertFalse(workspace["receipt"].exists())

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_unwritable_receipt_destination_is_refused_before_review(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            workspace["receipt"] = Path(tempdir) / "missing-dir" / "receipt.json"
            result = self.run_cli(workspace)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--receipt-output output destination is not writable", result.stderr)
            self.assertFalse(workspace["record"].exists(), "no engine may run for an unwritable receipt")

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_dry_run_preserves_an_existing_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = self.make_workspace(Path(tempdir))
            first = self.run_cli(workspace)
            self.assertEqual(first.returncode, 0, first.stderr)
            before = workspace["receipt"].read_bytes()
            dry = self.run_cli(workspace, "--dry-run")
            self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
            self.assertTrue(workspace["receipt"].exists(), "a dry run must not delete an existing receipt")
            self.assertEqual(workspace["receipt"].read_bytes(), before)

    def branch_workspace(self, tempdir: Path) -> tuple[dict[str, object], Path, str, str, list[str]]:
        workspace = self.make_workspace(tempdir)
        repo = workspace["repo"]
        base_sha = git(repo, "rev-parse", "HEAD").strip()
        git(repo, "branch", "movable", base_sha)
        git(repo, "add", "a.txt")
        git(repo, "commit", "-qm", "reviewed change")
        head_sha = git(repo, "rev-parse", "HEAD").strip()
        argv = ["--mode", "branch", "--base", "movable", "--engine", "codex",
                "--codex-bin", str(workspace["codex_bin"]),
                "--receipt-output", str(workspace["receipt"])]
        return workspace, repo, base_sha, head_sha, argv

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_base_ref_moving_away_and_back_during_bundling_is_a_source_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace, repo, base_sha, head_sha, argv = self.branch_workspace(Path(tempdir))
            original_bundle = self.helper["branch_bundle"]
            seen: dict[str, object] = {}

            def aba_branch_bundle(repo_path, base_ref, *args, **kwargs):
                git(repo, "update-ref", "refs/heads/movable", head_sha)
                captured = original_bundle(repo_path, base_ref, *args, **kwargs)
                seen["base"] = captured.base
                git(repo, "update-ref", "refs/heads/movable", base_sha)
                return captured

            exit_code, raised, _, stderr = self.run_main(
                workspace, argv, {"branch_bundle": aba_branch_bundle},
            )
            self.assertEqual(seen["base"], head_sha, "fixture must cut the bundle from the moved ref")
            self.assertIsNone(exit_code, stderr)
            self.assertIsInstance(raised, SystemExit)
            self.assertIn("cut from merge-base", str(raised.code))
            _, payload = self.load_receipt(workspace)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["error"]["kind"], "source_mutation")
            self.assertFalse(workspace["record"].exists(), "no engine may run on an A-B-A bundle")

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_head_moving_away_and_back_during_bundling_is_a_source_mutation(self) -> None:
        # PAR-1287: reviewed_commit comes from the initial snapshot, but
        # branch_bundle re-resolves HEAD. A HEAD that moves away and back leaves
        # every snapshot comparison equal, so the bundle's own commit must match.
        with tempfile.TemporaryDirectory() as tempdir:
            workspace, repo, base_sha, head_sha, argv = self.branch_workspace(Path(tempdir))
            head_ref = git(repo, "symbolic-ref", "HEAD").strip()
            original_bundle = self.helper["branch_bundle"]
            seen: dict[str, object] = {}

            def aba_head_bundle(repo_path, base_ref, *args, **kwargs):
                git(repo, "update-ref", head_ref, base_sha)
                captured = original_bundle(repo_path, base_ref, *args, **kwargs)
                seen["commit"] = captured.commit
                git(repo, "update-ref", head_ref, head_sha)
                return captured

            exit_code, raised, stdout, stderr = self.run_main(
                workspace, argv, {"branch_bundle": aba_head_bundle},
            )
            self.assertEqual(seen["commit"], base_sha, "fixture must cut the bundle from the moved HEAD")
            self.assertEqual(git(repo, "rev-parse", "HEAD").strip(), head_sha, "fixture must restore HEAD")
            self.assertIsNone(exit_code, stderr)
            self.assertIsInstance(raised, SystemExit)
            self.assertIn("HEAD moved", str(raised.code))
            _, payload = self.load_receipt(workspace)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["error"]["kind"], "source_mutation")
            self.assertNotIn("scoped-clean", stdout, "no clean verdict may be printed for an unreviewed commit")
            self.assertFalse(workspace["record"].exists(), "no engine may run on a bundle cut from another HEAD")

    @unittest.skipIf(os.name == "nt", "the fake executables are POSIX-only")
    def test_base_ref_moving_during_the_review_is_a_source_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace, repo, base_sha, head_sha, argv = self.branch_workspace(Path(tempdir))
            original_engine = self.helper["run_engine"]

            def moving_engine(*args, **kwargs):
                git(repo, "update-ref", "refs/heads/movable", head_sha)
                return original_engine(*args, **kwargs)

            exit_code, raised, stdout, stderr = self.run_main(
                workspace, argv, {"run_engine": moving_engine},
            )
            self.assertTrue(workspace["record"].exists(), "fixture must reach the engine")
            self.assertIsNone(exit_code, stderr)
            self.assertIsInstance(raised, SystemExit)
            self.assertIn("while the review ran", str(raised.code))
            envelope, payload = self.load_receipt(workspace)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["error"]["kind"], "source_mutation")
            self.assertNotIn("scoped-clean", stdout, "no clean verdict may be printed after the base moved")


if __name__ == "__main__":
    unittest.main()
