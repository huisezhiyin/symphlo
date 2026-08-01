from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from symphlo.local_app import _resolve_web_root


REQUIRED_ASSETS = (
    "flow-console/index.html",
    "flow-console/assets/app.js",
    "flow-console/assets/styles.css",
    "flow-console/assets/flow-canvas.js",
    "flow-console/assets/flow-canvas.css",
)


def install_assets(root: Path) -> Path:
    for relative in REQUIRED_ASSETS:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(relative, encoding="utf-8")
    return root


class LocalAppAssetResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_explicit_root_is_authoritative(self) -> None:
        explicit = install_assets(self.root / "explicit")
        packaged = install_assets(self.root / "packaged")
        resolved = _resolve_web_root(
            self.workspace,
            explicit,
            packaged_web_root=packaged,
        )
        self.assertEqual(resolved, explicit.resolve())

    def test_invalid_explicit_root_does_not_silently_fallback(self) -> None:
        packaged = install_assets(self.root / "packaged")
        with self.assertRaisesRegex(RuntimeError, "explicit root"):
            _resolve_web_root(
                self.workspace,
                self.root / "missing",
                packaged_web_root=packaged,
            )

    def test_development_build_precedes_packaged_assets(self) -> None:
        development = install_assets(self.workspace / "apps" / "web" / "dist")
        packaged = install_assets(self.root / "packaged")
        resolved = _resolve_web_root(
            self.workspace,
            packaged_web_root=packaged,
        )
        self.assertEqual(resolved, development.resolve())

    def test_installed_assets_are_used_without_a_source_checkout(self) -> None:
        packaged = install_assets(self.root / "packaged")
        resolved = _resolve_web_root(
            self.workspace,
            packaged_web_root=packaged,
        )
        self.assertEqual(resolved, packaged.resolve())

    def test_incomplete_assets_fail_with_actionable_message(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "make web-build"):
            _resolve_web_root(
                self.workspace,
                packaged_web_root=self.root / "missing-packaged",
            )


if __name__ == "__main__":
    unittest.main()
