from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PublicSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.script = self.root / "scripts" / "check_public_source.py"

    def test_export_is_exact_and_self_validating(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "public"
            exported = subprocess.run(
                [sys.executable, str(self.script), "--export", str(destination)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(exported.returncode, 0, exported.stderr)
            self.assertTrue((destination / "README.md").is_file())
            self.assertTrue((destination / ".github" / "workflows" / "ci.yml").is_file())
            for relative in (
                "LICENSE",
                "NOTICE",
                "pyproject.toml",
                "THIRD_PARTY.md",
                "SECURITY.md",
                "CONTRIBUTING.md",
            ):
                self.assertTrue((destination / relative).is_file(), relative)
            self.assertFalse((destination / "IMPLEMENTATION_BOOTSTRAP.md").exists())
            self.assertFalse((destination / "OPEN_SOURCE_REVIEW.md").exists())
            self.assertFalse((destination / "PROJECT_KNOWLEDGE.md").exists())
            self.assertFalse((destination / "docs" / "features").exists())

            checked = subprocess.run(
                [sys.executable, str(destination / "scripts" / "check_public_source.py")],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_export_refuses_non_empty_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            marker = destination / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            exported = subprocess.run(
                [sys.executable, str(self.script), "--export", str(destination)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(exported.returncode, 2)
            self.assertIn("must be absent or empty", exported.stderr)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_source_policy_rejects_private_and_local_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "public"
            exported = subprocess.run(
                [sys.executable, str(self.script), "--export", str(destination)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(exported.returncode, 0, exported.stderr)
            checker = destination / "scripts" / "check_public_source.py"

            def assert_rejected(relative: str, suffix: str, expected: str) -> None:
                path = destination / relative
                original = path.read_text(encoding="utf-8")
                path.write_text(original + suffix, encoding="utf-8")
                try:
                    checked = subprocess.run(
                        [sys.executable, str(checker)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(checked.returncode, 1)
                    self.assertIn(expected, checked.stderr)
                finally:
                    path.write_text(original, encoding="utf-8")

            assert_rejected(
                "README.md",
                "\n/" + "Users" + "/example/private\n",
                "private or local reference",
            )
            assert_rejected(
                "README.md",
                "\n" + "agent" + "_flow\n",
                "private or local reference",
            )
            assert_rejected(
                "README.md",
                "\napi_" + 'key = "not-a-real-secret"\n',
                "possible secret value",
            )
            assert_rejected(
                "pnpm-lock.yaml",
                "\nregistry: https" + "://packages." + "corp.example/npm/\n",
                "non-public package registry reference",
            )

            npmrc = destination / ".npmrc"
            npmrc.write_text(
                "registry=https://registry.npmjs.org/\n",
                encoding="utf-8",
            )
            checked = subprocess.run(
                [sys.executable, str(checker)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(checked.returncode, 1)
            self.assertIn("repository-local package manager config", checked.stderr)

    def test_public_entrypoints_do_not_reference_local_governance(self) -> None:
        local_only = re.compile(
            r"PROJECT_KNOWLEDGE\.md|IMPLEMENTATION_BOOTSTRAP\.md|"
            r"OPEN_SOURCE_REVIEW\.md|docs/features"
        )
        for relative in ("AGENTS.md", "PROJECT_SPEC.md", "README.md"):
            content = (self.root / relative).read_text(encoding="utf-8")
            self.assertIsNone(local_only.search(content), relative)

    def test_ci_actions_are_sha_pinned_and_read_only(self) -> None:
        workflow = (self.root / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        uses = re.findall(r"^\s*uses:\s*[^@\s]+@([^\s]+)", workflow, re.MULTILINE)
        self.assertTrue(uses)
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{40}", value) for value in uses))
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("NPM_CONFIG_REGISTRY: https://registry.npmjs.org/", workflow)
        self.assertIn("make check PYTHON_VERSION=3.12", workflow)
        self.assertIn("make demo PYTHON_VERSION=3.12", workflow)


if __name__ == "__main__":
    unittest.main()
