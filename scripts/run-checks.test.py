"""Self-tests for scripts/run-checks: preflight refusals and runner order.

Every refusal must stop before either runner starts. The runners are stubs that
record their invocation, so "no record" proves no slow step began. POSIX only:
run-checks is a bash gate; scripts/check-fork does not run this on Windows.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("run-checks")
TOOLS = ("bash", "cat", "cp", "dirname", "env", "mktemp", "rm", "sed", "tail", "tr")
STUB = """import os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
with open(os.environ["RUN_CHECKS_TEST_LOG"], "a", encoding="utf-8") as log:
    log.write(" ".join([name, *sys.argv[1:]]).rstrip() + "\\n")
if os.environ.get("RUN_CHECKS_TEST_ENV_LOG"):
    with open(os.environ["RUN_CHECKS_TEST_ENV_LOG"], "a", encoding="utf-8") as log:
        log.write(f"{name} TMPDIR={os.environ.get('TMPDIR')}\\n")
print(f"{name} stub output")
sys.exit(1 if os.environ.get("RUN_CHECKS_TEST_FAIL") == name else 0)
"""


@unittest.skipIf(os.name == "nt", "run-checks is a bash gate for POSIX machines")
class RunChecksTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.repo = self.base / "repo"
        (self.repo / "scripts").mkdir(parents=True)
        shutil.copy2(SCRIPT, self.repo / "scripts" / "run-checks")
        for name in ("check-skills", "check-fork"):
            (self.repo / "scripts" / name).write_text(STUB, encoding="utf-8")
        tsc = self.repo / "node_modules" / ".bin" / "tsc"
        tsc.parent.mkdir(parents=True)
        self.executable(tsc, "#!/bin/sh\nexit 0\n")
        self.bin = self.base / "bin"
        self.bin.mkdir()
        for tool in TOOLS:
            found = shutil.which(tool)
            self.assertIsNotNone(found, f"test needs {tool} on PATH")
            (self.bin / tool).symlink_to(found)
        self.executable(self.bin / "node", "#!/bin/sh\necho v0.0.0-fake\n")
        self.executable(self.bin / "npm", "#!/bin/sh\nexit 0\n")
        self.temp = self.base / "private-temp"
        self.temp.mkdir()
        self.log = self.base / "runners.log"
        self.environment = {
            "PATH": str(self.bin), "HOME": os.environ.get("HOME", str(self.base)),
            "PYTHON": sys.executable, "TMPDIR": str(self.temp),
            "RUN_CHECKS_TEST_LOG": str(self.log), "LC_ALL": "C",
        }

    def executable(self, path: Path, body: str) -> Path:
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
        return path

    def run_checks(self, **overrides: str | None) -> subprocess.CompletedProcess[str]:
        environment = dict(self.environment)
        for key, value in overrides.items():
            if value is None:
                environment.pop(key, None)
            else:
                environment[key] = value
        return subprocess.run(
            [str(self.bin / "bash"), str(self.repo / "scripts" / "run-checks")],
            cwd=self.base, env=environment, text=True, capture_output=True, timeout=60,
        )

    def runners(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []

    def assert_refused(self, result: subprocess.CompletedProcess[str], message: str) -> None:
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(message, result.stderr)
        self.assertEqual(self.runners(), [], "a runner started despite the refusal")
        self.assertNotIn("Traceback", result.stderr)

    def shadow(self, *modules: str) -> str:
        # A PYTHONPATH entry whose packages fail to import, as if not installed.
        directory = self.base / "shadow"
        for module in modules:
            package = directory / module
            package.mkdir(parents=True)
            (package / "__init__.py").write_text(
                f"raise ImportError('synthetic: {module} not installed')\n", encoding="utf-8")
        return str(directory)

    def test_ready_environment_runs_check_skills_then_check_fork(self) -> None:
        result = self.run_checks()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.runners(), ["check-skills", "check-fork"])
        self.assertIn("  ok    check-skills\n", result.stdout)
        self.assertIn("  ok    check-fork\n", result.stdout)
        self.assertIn("ALL CHECKS PASSED", result.stdout)
        self.assertEqual(list(self.temp.iterdir()), [], "log file left behind")

    def test_runners_get_the_resolved_temporary_directory(self) -> None:
        # The macOS default TMPDIR (/var/folders/...) runs through a symlink; the steps must
        # see the realpath, which upstream's windows-test-process self-test compares against.
        alias = self.base / "temp-alias"
        alias.symlink_to(self.temp, target_is_directory=True)
        env_log = self.base / "env.log"
        result = self.run_checks(TMPDIR=str(alias), RUN_CHECKS_TEST_ENV_LOG=str(env_log))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        resolved = str(self.temp.resolve())
        self.assertEqual(env_log.read_text(encoding="utf-8").splitlines(),
                         [f"check-skills TMPDIR={resolved}", f"check-fork TMPDIR={resolved}"])

    def test_runner_failure_is_reported_after_both_runners(self) -> None:
        for failing in ("check-skills", "check-fork"):
            with self.subTest(failing=failing):
                self.log.unlink(missing_ok=True)
                result = self.run_checks(RUN_CHECKS_TEST_FAIL=failing)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(self.runners(), ["check-skills", "check-fork"])
                self.assertIn(f"  FAIL  {failing}\n", result.stdout)
                self.assertIn(f"{failing} stub output", result.stdout)
                self.assertIn(f"  - {failing}\n", result.stderr)
                self.assertNotIn("ALL CHECKS PASSED", result.stdout)
                kept = [line.split("full log: ", 1)[1] for line in result.stdout.splitlines()
                        if "full log: " in line]
                self.assertEqual(len(kept), 1)
                self.assertTrue(Path(kept[0]).is_relative_to(self.temp))
                self.assertIn(f"{failing} stub output", Path(kept[0]).read_text(encoding="utf-8"))
                Path(kept[0]).unlink()
                self.assertEqual(list(self.temp.iterdir()), [])

    def test_refuses_missing_interpreter(self) -> None:
        self.assert_refused(self.run_checks(PYTHON="no-such-python-for-run-checks"), "not on PATH")

    def test_refuses_interpreter_without_pyyaml_or_pillow(self) -> None:
        for modules, message in (
            (("yaml",), "lacks PyYAML."),
            (("PIL",), "lacks Pillow."),
            (("yaml", "PIL"), "lacks PyYAML and Pillow."),
        ):
            with self.subTest(modules=modules):
                shutil.rmtree(self.base / "shadow", ignore_errors=True)
                result = self.run_checks(PYTHONPATH=self.shadow(*modules))
                self.assert_refused(result, message)
                self.assertIn("pip install -r requirements-dev.txt", result.stderr)

    def test_refuses_bare_interpreter_without_site_packages(self) -> None:
        bare = self.executable(self.base / "bare-python",
                               f"#!/bin/sh\nexec {shlex.quote(sys.executable)} -S \"$@\"\n")
        self.assert_refused(self.run_checks(PYTHON=str(bare)), "lacks PyYAML and Pillow.")

    def test_refuses_interpreter_inside_checkout(self) -> None:
        venv = self.repo / ".venv" / "bin"
        venv.mkdir(parents=True)
        wrapper = self.executable(venv / "python", f"#!/bin/sh\nexec {shlex.quote(sys.executable)} \"$@\"\n")
        (venv / "python3").symlink_to(sys.executable)
        for interpreter in (str(wrapper), str(venv / "python3")):
            with self.subTest(interpreter=interpreter):
                self.assert_refused(self.run_checks(PYTHON=interpreter), "is inside the checkout")
        # Found on PATH by name, as an activated in-repo venv would be.
        self.assert_refused(self.run_checks(PYTHON="python3", PATH=f"{venv}:{self.bin}"),
                            "is inside the checkout")

    def test_refuses_temporary_directory_inside_checkout(self) -> None:
        inside = self.repo / "tmp"
        inside.mkdir()
        self.assert_refused(self.run_checks(TMPDIR=str(inside)), "is inside the checkout")

    @unittest.skipUnless(sys.platform == "darwin", "autoreview refuses shared scratch only on macOS")
    def test_refuses_shared_scratch_temporary_directory_on_macos(self) -> None:
        try:
            scratch = tempfile.mkdtemp(prefix="run-checks-test.", dir="/tmp")
        except OSError:
            scratch = "/tmp"  # gettempdir still lands on a scratch root or refuses
        else:
            self.addCleanup(shutil.rmtree, scratch, True)
        for overrides in ({"TMPDIR": scratch}, {"TMPDIR": None, "TEMP": scratch}, {"TMPDIR": "/private/var/tmp"}):
            with self.subTest(overrides=overrides):
                self.assert_refused(self.run_checks(**overrides), "shared scratch directory")

    def test_refuses_missing_node_toolchain(self) -> None:
        for tool in ("node", "npm"):
            with self.subTest(tool=tool):
                hidden = self.bin / tool
                saved = hidden.read_text(encoding="utf-8")
                hidden.unlink()
                try:
                    self.assert_refused(self.run_checks(), f"{tool} not on PATH")
                finally:
                    self.executable(hidden, saved)

    def test_refuses_missing_node_modules(self) -> None:
        shutil.rmtree(self.repo / "node_modules")
        self.assert_refused(self.run_checks(), "npm ci --ignore-scripts")


if __name__ == "__main__":
    unittest.main()
