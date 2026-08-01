"""Build the Python distribution with the prebuilt Local App assets."""

from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.errors import SetupError


ROOT = Path(__file__).resolve().parent
WEB_DIST = ROOT / "apps" / "web" / "dist"
SESSION_FIXTURE = ROOT / "examples" / "agents" / "stdio_fixture_agent.py"
REQUIRED_WEB_ASSETS = (
    "flow-console/index.html",
    "flow-console/assets/app.js",
    "flow-console/assets/styles.css",
    "flow-console/assets/flow-canvas.js",
    "flow-console/assets/flow-canvas.css",
)


class BuildPyWithWeb(build_py):
    """Copy one fresh Vite build into the installable Python package."""

    def run(self) -> None:
        missing = [
            relative
            for relative in REQUIRED_WEB_ASSETS
            if not (WEB_DIST / relative).is_file()
        ]
        if missing:
            raise SetupError(
                "Local App web build is incomplete; run `pnpm web:build` before "
                f"building the wheel (missing: {', '.join(missing)})"
            )
        if not SESSION_FIXTURE.is_file():
            raise SetupError(
                "session protocol fixture is missing; expected "
                "examples/agents/stdio_fixture_agent.py"
            )
        super().run()
        build_root = Path(self.build_lib).resolve()
        target = (build_root / "symphlo" / "_web").resolve()
        try:
            target.relative_to(build_root)
        except ValueError as error:  # pragma: no cover - defensive path invariant
            raise SetupError("refusing to stage Web assets outside build_lib") from error
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(WEB_DIST, target)
        fixture_target = build_root / "symphlo" / "_fixtures" / SESSION_FIXTURE.name
        fixture_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SESSION_FIXTURE, fixture_target)


setup(cmdclass={"build_py": BuildPyWithWeb})
