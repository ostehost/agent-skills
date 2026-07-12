from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("validate-skills")


class ValidateSkillsTest(unittest.TestCase):
    def run_validator(
        self, skills: dict[str, str] | None, manifest: object | str | None = None
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / "scripts").mkdir(parents=True)
            shutil.copy2(SCRIPT, repo / "scripts" / "validate-skills")
            for name, content in (skills or {}).items():
                skill_dir = repo / "skills" / name
                skill_dir.mkdir(parents=True)
                (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
            if manifest is not None:
                manifest_text = (
                    manifest if isinstance(manifest, str) else json.dumps(manifest)
                )
                (repo / "skills.sh.json").write_text(manifest_text, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(repo / "scripts" / "validate-skills")],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_valid_frontmatter(self) -> None:
        result = self.run_validator(
            {
                "sample": (
                    '---\nname: sample\ndescription: "Example skill."\n'
                    'metadata:\n  version: "1"\n---\n# Sample\n'
                )
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "validated 1 skills\n")

    def test_missing_frontmatter(self) -> None:
        result = self.run_validator({"sample": "# Sample\n"})

        self.assertEqual(result.returncode, 1)
        self.assertIn("missing YAML frontmatter", result.stderr)

    def test_unterminated_frontmatter(self) -> None:
        result = self.run_validator({"sample": "---\nname: sample\n"})

        self.assertEqual(result.returncode, 1)
        self.assertIn("unterminated YAML frontmatter", result.stderr)

    def test_invalid_yaml(self) -> None:
        result = self.run_validator(
            {"sample": '---\nname: [sample\ndescription: "Example"\n---\n'}
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid YAML", result.stderr)

    def test_frontmatter_must_be_mapping(self) -> None:
        result = self.run_validator({"sample": "---\n- sample\n---\n"})

        self.assertEqual(result.returncode, 1)
        self.assertIn("YAML frontmatter must be a mapping", result.stderr)

    def test_required_fields_must_be_nonempty_strings(self) -> None:
        result = self.run_validator(
            {"sample": '---\nname: true\ndescription: "  "\n---\n'}
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("missing name", result.stderr)
        self.assertIn("missing description", result.stderr)

    def test_name_must_match_skill_directory(self) -> None:
        result = self.run_validator(
            {"sample": '---\nname: another\ndescription: "Example"\n---\n'}
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("does not match directory", result.stderr)

    def test_valid_manifest(self) -> None:
        result = self.run_validator(
            {"sample": '---\nname: sample\ndescription: "Example"\n---\n'},
            {"groupings": [{"title": "Examples", "skills": ["sample"]}]},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("validated skills.sh.json against 1 skills", result.stdout)

    def test_manifest_rejects_unknown_and_duplicate_skills(self) -> None:
        result = self.run_validator(
            {"sample": '---\nname: sample\ndescription: "Example"\n---\n'},
            {
                "groupings": [
                    {"title": "One", "skills": ["sample", "missing"]},
                    {"title": "Two", "skills": ["sample"]},
                ]
            },
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("references unknown skill 'missing'", result.stderr)
        self.assertIn("skill 'sample' is listed more than once", result.stderr)

    def test_manifest_rejects_invalid_shapes(self) -> None:
        cases = [
            ([], "top-level value must be a JSON object"),
            ({}, 'missing "groupings" array'),
            ({"groupings": {}}, '"groupings" must be an array'),
            ({"groupings": ["sample"]}, "grouping #1 must be an object"),
            (
                {"groupings": [{"title": "Examples", "skills": [None]}]},
                "non-string skill entry",
            ),
        ]
        for manifest, message in cases:
            with self.subTest(message=message):
                result = self.run_validator(
                    {"sample": '---\nname: sample\ndescription: "Example"\n---\n'},
                    manifest,
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)

    def test_manifest_rejects_invalid_json(self) -> None:
        result = self.run_validator(
            {"sample": '---\nname: sample\ndescription: "Example"\n---\n'},
            "{not json",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid JSON", result.stderr)

    def test_aliases_are_rejected(self) -> None:
        result = self.run_validator(
            {
                "sample": (
                    '---\nname: &name sample\ndescription: *name\n---\n'
                )
            }
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("YAML aliases are not allowed", result.stderr)

    def test_unsafe_tags_are_rejected(self) -> None:
        result = self.run_validator(
            {
                "sample": (
                    "---\nname: sample\n"
                    "description: !!python/object/apply:os.system ['false']\n---\n"
                )
            }
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid YAML", result.stderr)

    def test_no_skills(self) -> None:
        result = self.run_validator(None)

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "No skills/*/SKILL.md files found.\n")


if __name__ == "__main__":
    unittest.main()
