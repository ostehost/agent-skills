"""Self-tests for scripts/check-fork, including negative manifest fixtures."""
from __future__ import annotations

import contextlib
import io
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("check-fork")
ROOT = SCRIPT.resolve().parent.parent
HELPER = runpy.run_path(str(SCRIPT))
MAIN = HELPER["main"]
UPSTREAM_SUPPORT = ("check-skills", "windows_test_process.py")


class CheckForkTest(unittest.TestCase):
    @contextlib.contextmanager
    def checkout(self):
        """A minimal checkout whose manifest is green: every gated file exists."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            (root / "scripts").mkdir(parents=True)
            shutil.copy2(SCRIPT, root / "scripts" / "check-fork")
            for name in UPSTREAM_SUPPORT:
                shutil.copy2(ROOT / "scripts" / name, root / "scripts" / name)
            upstream = HELPER["load_check_skills"](ROOT)
            _, named = HELPER["check_skills_paths"](ROOT, upstream)
            listed = {*named, *HELPER["fork_gated_paths"](), *HELPER["FORK_COMPILE"],
                      *HELPER["KNOWN_UNGATED"]}
            for relative in listed:
                path = root.joinpath(*relative.split("/"))
                if not path.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("# fixture placeholder\n", encoding="utf-8")
            yield root

    def errors(self, root: Path) -> list[str]:
        return HELPER["manifest_errors"](root)

    def assert_manifest_red(self, root: Path, *fragments: str) -> None:
        errors = self.errors(root)
        self.assertTrue(errors, "manifest stayed green")
        joined = "\n".join(errors)
        for fragment in fragments:
            self.assertIn(fragment, joined)
        result = subprocess.run([sys.executable, str(root / "scripts/check-fork"), "--manifest-only"],
                                cwd=root, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_checkout_manifest_is_green(self) -> None:
        self.assertEqual(self.errors(ROOT), [])

    def test_fixture_manifest_is_green(self) -> None:
        # Control for the negative fixtures below: only their mutation turns it red.
        with self.checkout() as root:
            self.assertEqual(self.errors(root), [])
            result = subprocess.run([sys.executable, str(root / "scripts/check-fork"), "--manifest-only"],
                                    cwd=root, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unlisted_fork_test_file_is_red(self) -> None:
        with self.checkout() as root:
            (root / "fork-tests/autoreview/test_unlisted.py").write_text("", encoding="utf-8")
            self.assert_manifest_red(root, "not run by check-skills or check-fork",
                                     "fork-tests/autoreview/test_unlisted.py")

    def test_ungated_new_test_files_are_red(self) -> None:
        for relative in ("skills/beam/scripts/new-feature.test.mjs", "skills/new-skill/tests/test_new.py",
                         "skills/new-skill/scripts/thing_test.py", "scripts/new-tool.test.py",
                         "skills/design-competition/scripts/extra.test.sh"):
            with self.subTest(path=relative), self.checkout() as root:
                path = root.joinpath(*relative.split("/"))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")
                self.assert_manifest_red(root, relative)

    def test_fixtures_and_dependencies_are_not_test_files(self) -> None:
        with self.checkout() as root:
            for relative in ("skills/autoreview/tests/fixtures/test_data.py",
                             "node_modules/pkg/index.test.js"):
                path = root.joinpath(*relative.split("/"))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")
            self.assertEqual(self.errors(root), [])

    def test_missing_listed_module_is_red(self) -> None:
        for relative in (*HELPER["FORK_PYTHON_SUITES"], *HELPER["FORK_NODE_TESTS"],
                         "scripts/run-checks.test.py"):
            with self.subTest(path=relative), self.checkout() as root:
                root.joinpath(*relative.split("/")).unlink()
                self.assert_manifest_red(root, f"listed fork check is missing: {relative}")

    def test_stale_or_gated_known_ungated_entry_is_red(self) -> None:
        with self.checkout() as root:
            (root / "scripts/installed-autoreview.test.py").unlink()
            self.assert_manifest_red(root, "KNOWN_UNGATED entry no longer exists")
        with self.checkout() as root, mock.patch.dict(
                HELPER["KNOWN_UNGATED"], {"scripts/check-fork.test.py": "synthetic"}):
            self.assertIn("KNOWN_UNGATED entry is gated", "\n".join(self.errors(root)))

    def test_fork_test_back_in_upstream_directory_is_red(self) -> None:
        with self.checkout() as root:
            moved = root / "skills/autoreview/tests/test_receipt_contract.py"
            shutil.copyfile(root / "fork-tests/autoreview/test_receipt_contract.py", moved)
            self.assert_manifest_red(root, "skills/autoreview/tests/test_receipt_contract.py is not in "
                                           "check-skills TEST_MODULES")

    def upstream_manifest_test(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(root / "scripts/check-skills.test.py"),
             "CheckSkillsTest.test_manifest_covers_checkout_test_files_in_their_groups"],
            cwd=root, capture_output=True, text=True, timeout=120,
        )

    def test_fork_test_in_upstream_directory_fails_upstream_manifest_test(self) -> None:
        # D2 proof against a temporary copy of upstream's own self-test.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            (root / "scripts").mkdir(parents=True)
            for name in ("check-skills", "check-skills.test.py", "windows_test_process.py",
                         "windows-test-process.test.py"):
                shutil.copy2(ROOT / "scripts" / name, root / "scripts" / name)
            core = root / "skills/autoreview/scripts/autoreview_test.py"
            core.parent.mkdir(parents=True)
            shutil.copy2(ROOT / "skills/autoreview/scripts/autoreview_test.py", core)
            tests = root / "skills/autoreview/tests"
            tests.mkdir(parents=True)
            for source in (ROOT / "skills/autoreview/tests").glob("test_*.py"):
                shutil.copy2(source, tests / source.name)
            control = self.upstream_manifest_test(root)
            self.assertEqual(control.returncode, 0, control.stdout + control.stderr)
            for name in ("test_receipt_contract.py", "test_merge_invariants.py"):
                with self.subTest(name=name):
                    shutil.copy2(ROOT / "fork-tests/autoreview" / name, tests / name)
                    result = self.upstream_manifest_test(root)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("FAIL: test_manifest_covers_checkout_test_files_in_their_groups",
                                  result.stderr)
                    self.assertIn(f"skills/autoreview/tests/{name}", result.stderr)
                    (tests / name).unlink()

    def commands(self, root: Path, args: list[str], *, which=None, status=0):
        with mock.patch("shutil.which", side_effect=which or (lambda name: name)), \
                mock.patch("subprocess.run", return_value=subprocess.CompletedProcess([], status)) as run, \
                mock.patch.dict(HELPER["main"].__globals__, {"manifest_errors": lambda root: []}), \
                contextlib.redirect_stdout(io.StringIO()) as out, \
                contextlib.redirect_stderr(io.StringIO()) as err:
            code = MAIN(args, root=root)
        for call in run.call_args_list:
            self.assertEqual(call.kwargs, {"cwd": root})
        commands = [list(call.args[0]) for call in run.call_args_list]
        for command in commands:
            if command[1:2] == ["-X"]:
                self.assertTrue(command[2].startswith("pycache_prefix="))
                self.assertFalse(Path(command[2].removeprefix("pycache_prefix=")).exists())
                command[2] = "pycache_prefix=<temporary>"
        return code, commands, out.getvalue(), err.getvalue()

    def test_default_runs_every_fork_step_in_order(self) -> None:
        code, commands, _, _ = self.commands(ROOT, [])
        self.assertEqual(code, 0)
        python = sys.executable
        self.assertEqual(commands[0][:5], [python, "-X", "pycache_prefix=<temporary>", "-m", "py_compile"])
        self.assertCountEqual(commands[0][5:], HELPER["FORK_COMPILE"])
        tail = [command[1:] for command in commands[1:]]
        expected = [["scripts/check-fork.test.py"]]
        if os.name != "nt":
            expected.append(["scripts/run-checks.test.py"])
        expected += [["scripts/check-fork", "--tests-only"],
                     ["--test", "skills/beam/scripts/beam-handoff.test.mjs"],
                     ["skills/design-competition/scripts/check-conformance.sh"],
                     ["skills/design-competition/scripts/scripts.test.sh"]]
        self.assertEqual(tail, expected)
        self.assertEqual([command[0] for command in commands[-3:]], ["node", "bash", "bash"])

    def test_skip_flag_drops_only_design_competition(self) -> None:
        _, full, _, _ = self.commands(ROOT, [])
        code, skipped, out, _ = self.commands(ROOT, ["--skip-design-competition"])
        self.assertEqual(code, 0)
        self.assertEqual(skipped, full[:-2])
        self.assertIn("skip: design-competition suites", out)
        self.assertFalse(any("design-competition" in " ".join(command) for command in skipped))

    def test_missing_jq_without_skip_flag_fails(self) -> None:
        for tool in ("jq", "bash"):
            with self.subTest(tool=tool):
                which = lambda name: None if name == tool else name  # noqa: E731
                code, commands, _, err = self.commands(ROOT, [], which=which)
                self.assertEqual(code, 1)
                self.assertIn(f"required executable not found: {tool}", err)
                self.assertIn(f"design-competition ({tool} missing)", err)
                self.assertFalse(any("design-competition" in " ".join(command) for command in commands))
                # Other steps still ran: the failure is reported, not a stop.
                self.assertTrue(any("--tests-only" in command for command in commands))

    def test_failing_step_is_reported_and_nonzero(self) -> None:
        code, commands, _, err = self.commands(ROOT, [], status=3)
        self.assertEqual(code, 1)
        self.assertGreater(len(commands), 4)
        self.assertIn("FAILED (3): fork python suites", err)

    def test_missing_executable_is_a_failure(self) -> None:
        code, commands, _, err = self.commands(ROOT, [], which=lambda name: None if name == "node" else name)
        self.assertEqual(code, 1)
        self.assertIn("required executable not found: node", err)
        self.assertNotIn("node", [command[0] for command in commands])

    def test_manifest_failure_fails_the_run(self) -> None:
        with self.checkout() as root:
            (root / "fork-tests/autoreview/test_unlisted.py").write_text("", encoding="utf-8")
            with mock.patch("subprocess.run") as run, contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(MAIN(["--manifest-only"], root=root), 1)
            run.assert_not_called()
            self.assertIn("test_unlisted.py", err.getvalue())

    def test_checkout_executable_modes_are_green(self) -> None:
        self.assertEqual(HELPER["executable_mode_errors"](ROOT), [])

    @unittest.skipIf(os.name == "nt", "executable bits are POSIX-only")
    def test_shebang_script_without_executable_bit_is_red(self) -> None:
        with self.checkout() as root:
            tool = root / "skills" / "some-skill" / "scripts" / "tool"
            tool.parent.mkdir(parents=True)
            tool.write_text("#!/usr/bin/env bash\necho hi\n", encoding="utf-8")
            tool.chmod(0o755)
            # Control: test modules and helpers with a shebang may stay 0644.
            for name in ("test_thing.py", "thing.test.py", "test-helper.py"):
                helper = tool.with_name(name)
                helper.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
                helper.chmod(0o644)
            self.assertEqual(HELPER["executable_mode_errors"](root), [])
            tool.chmod(0o644)
            errors = HELPER["executable_mode_errors"](root)
            self.assertEqual(errors, ["script with a shebang lost its executable bit: "
                                      "skills/some-skill/scripts/tool"])
            result = subprocess.run([sys.executable, str(root / "scripts/check-fork"), "--manifest-only"],
                                    cwd=root, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("lost its executable bit: skills/some-skill/scripts/tool", result.stderr)

    @unittest.skipIf(os.name == "nt", "executable bits are POSIX-only")
    def test_real_fork_executables_losing_their_bit_are_red(self) -> None:
        # The two cases the adversarial pass proved invisible to every suite.
        for relative in ("skills/agent-transcript/scripts/agent-transcript",
                         "skills/design-competition/scripts/check-conformance.sh"):
            with self.subTest(path=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "repo"
                target = root.joinpath(*relative.split("/"))
                target.parent.mkdir(parents=True)
                shutil.copy2(ROOT.joinpath(*relative.split("/")), target)
                self.assertEqual(HELPER["executable_mode_errors"](root), [])
                target.chmod(0o644)
                self.assertEqual(HELPER["executable_mode_errors"](root),
                                 [f"script with a shebang lost its executable bit: {relative}"])

    @contextlib.contextmanager
    def suite_checkout(self, bodies: dict[str, str]):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            (root / "scripts").mkdir(parents=True)
            shutil.copy2(SCRIPT, root / "scripts" / "check-fork")
            for name in UPSTREAM_SUPPORT:
                shutil.copy2(ROOT / "scripts" / name, root / "scripts" / name)
            for relative in HELPER["FORK_PYTHON_SUITES"]:
                path = root.joinpath(*relative.split("/"))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(bodies.get(relative, bodies.get("*", "")), encoding="utf-8")
            yield root

    def run_suites(self, root: Path) -> subprocess.CompletedProcess[str]:
        environment = {**os.environ, "OPENAI_API_KEY": "synthetic-operator-key",
                       "CODEX_HOME": str(root.parent / "operator-codex"), "PYTHONIOENCODING": "utf-8"}
        return subprocess.run([sys.executable, str(root / "scripts/check-fork"), "--tests-only"],
                              cwd=root.parent, env=environment, capture_output=True, text=True,
                              encoding="utf-8", timeout=120)

    def test_suites_run_from_checkout_files_in_scrubbed_environment(self) -> None:
        body = (
            "import os, unittest\nfrom pathlib import Path\n"
            "class Cases(unittest.TestCase):\n"
            "    def test_scrubbed(self):\n"
            "        self.assertNotIn('OPENAI_API_KEY', os.environ)\n"
            "        self.assertNotIn('CODEX_HOME', os.environ)\n"
            "        self.assertTrue(Path.home().name.startswith('.check-skills-home.'))\n"
        )
        count = len(HELPER["FORK_PYTHON_SUITES"])
        with self.suite_checkout({"*": body}) as root:
            result = self.run_suites(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            started = [line for line in result.stderr.splitlines() if line.startswith("test start: ")]
            self.assertEqual(len(started), count)
            for relative in HELPER["FORK_PYTHON_SUITES"]:
                self.assertIn(Path(relative).stem, result.stderr)
            self.assertIn(f"Ran {count} tests", result.stderr)

    def test_suite_failure_and_broken_discovery_are_red(self) -> None:
        passing = "import unittest\nclass Cases(unittest.TestCase):\n    def test_ok(self): pass\n"
        failing = "import unittest\nclass Cases(unittest.TestCase):\n    def test_bad(self): self.fail('synthetic')\n"
        first = HELPER["FORK_PYTHON_SUITES"][0]
        for body, diagnostic in ((failing, "FAILED (failures=1)"),
                                 ("syntax error!", "test discovery failed"),
                                 ("", "empty or duplicate")):
            with self.subTest(diagnostic=diagnostic):
                bodies = {"*": passing if body else "", first: body}
                with self.suite_checkout(bodies) as root:
                    result = self.run_suites(root)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn(diagnostic, result.stderr)


if __name__ == "__main__":
    bootstrap = runpy.run_path(str(SCRIPT.with_name("windows_test_process.py")))
    status = bootstrap["ensure_windows_test_process"](sys.argv[0], sys.argv[1:])
    if status is not None:
        bootstrap["exit_test_process"](status)
    unittest.main()
