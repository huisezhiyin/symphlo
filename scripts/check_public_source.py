"""Validate and export the fail-closed Symphlo public source projection."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Sequence
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "AGENTS.md",
    "LICENSE",
    "Makefile",
    "NOTICE",
    "package.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
    "pyproject.toml",
    "PROJECT_SPEC.md",
    "PUBLIC_SOURCE_MANIFEST.md",
    "README.md",
    "THIRD_PARTY.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
)
REQUIRED_DIRECTORIES = (
    ".github/workflows",
    "apps/desktop",
    "apps/web",
    "docs/demo",
    "docs/vision",
    "examples/agents",
    "examples/capabilities",
    "examples/flows",
    "scripts",
    "src/symphlo",
    "tests",
)
OPTIONAL_RELEASE_FILES: tuple[str, ...] = ()
FORBIDDEN_REPOSITORY_FILES = (".npmrc",)
SKIP_PARTS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    ".cache",
    "test-results",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
}
FORBIDDEN_PUBLIC_TEXT = (
    re.compile(r"/Users/"),
    re.compile(r"\bagent_flow\b", re.IGNORECASE),
    re.compile(r"\bwukong\b", re.IGNORECASE),
    re.compile(r"\bdify\b", re.IGNORECASE),
)
SECRET_VALUE = re.compile(
    r"(?i)(api[_-]?key|access[_-]?key|secret[_-]?key|client[_-]?secret)\s*[:=]\s*['\"][^'\"]{8,}['\"]"
)
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\((?!https?://|#)([^)]+)\)")
PUBLIC_ENTRYPOINTS = {
    Path("AGENTS.md"),
    Path("PROJECT_SPEC.md"),
    Path("README.md"),
}
LOCAL_ONLY_REFERENCE = re.compile(
    r"PROJECT_KNOWLEDGE\.md|IMPLEMENTATION_BOOTSTRAP\.md|"
    r"OPEN_SOURCE_REVIEW\.md|docs/features"
)
REGISTRY_REFERENCE = re.compile(
    r"(?i)(?:npm_config_registry|--registry|registry)"
    r"\s*(?:[:=]|\s)\s*[\"']?(https?://[^\s<>'\"`]+)"
)
HTTP_URL = re.compile(r"https?://[^\s<>'\"`]+")
PUBLIC_PACKAGE_HOSTS = {
    "registry.npmjs.org",
    "www.npmjs.com",
    "npmjs.com",
    "github.com",
    "codeload.github.com",
}


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser()
    command.add_argument("--export", type=Path, help="Copy the public projection to an empty directory.")
    return command


def public_files(root: Path) -> tuple[Path, ...]:
    files: set[Path] = set()
    for relative in (*REQUIRED_FILES, *OPTIONAL_RELEASE_FILES):
        path = root / relative
        if path.is_file() or path.is_symlink():
            files.add(path)
    for relative in REQUIRED_DIRECTORIES:
        directory = root / relative
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and not any(part in SKIP_PARTS for part in path.relative_to(root).parts):
                files.add(path)
    return tuple(sorted(files))


def validate(root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    for relative in FORBIDDEN_REPOSITORY_FILES:
        path = root / relative
        if path.exists() or path.is_symlink():
            failures.append(f"repository-local package manager config is not allowed: {relative}")
    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            failures.append(f"missing required public file: {relative}")
    for relative in REQUIRED_DIRECTORIES:
        if not (root / relative).is_dir():
            failures.append(f"missing required public directory: {relative}")

    files = public_files(root)
    public_paths = {path.resolve() for path in files}
    for path in files:
        relative = path.relative_to(root)
        if path.is_symlink():
            failures.append(f"symlink is not allowed: {relative}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SECRET_VALUE.search(text):
            failures.append(f"possible secret value: {relative}")
        if relative != Path("scripts/check_public_source.py") and any(
            pattern.search(text) for pattern in FORBIDDEN_PUBLIC_TEXT
        ):
            failures.append(f"private or local reference in public file: {relative}")
        if relative in PUBLIC_ENTRYPOINTS and LOCAL_ONLY_REFERENCE.search(text):
            failures.append(f"local-only reference in public entrypoint: {relative}")
        for registry_url in REGISTRY_REFERENCE.findall(text):
            host = (urlsplit(registry_url.rstrip(").,;]")).hostname or "").lower()
            if host not in PUBLIC_PACKAGE_HOSTS:
                failures.append(
                    f"non-public package registry reference: {relative} -> {host or registry_url}"
                )
        if relative == Path("pnpm-lock.yaml"):
            for package_url in HTTP_URL.findall(text):
                host = (urlsplit(package_url.rstrip(").,;]")).hostname or "").lower()
                if host not in PUBLIC_PACKAGE_HOSTS:
                    failures.append(
                        f"non-public package source in lockfile: {relative} -> "
                        f"{host or package_url}"
                    )
        if path.suffix == ".md":
            for raw_target in MARKDOWN_LINK.findall(text):
                target = raw_target.split("#", 1)[0]
                if not target:
                    continue
                resolved = (path.parent / target).resolve()
                try:
                    resolved.relative_to(root.resolve())
                except ValueError:
                    failures.append(f"public Markdown link escapes tree: {relative} -> {raw_target}")
                    continue
                if resolved not in public_paths:
                    failures.append(f"broken public Markdown link: {relative} -> {raw_target}")
    return tuple(failures)


def export_public_tree(source: Path, destination: Path) -> int:
    destination = destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        print(f"public export destination must be absent or empty: {destination}", file=sys.stderr)
        return 2
    failures = validate(source)
    if failures:
        _print_failures(failures)
        return 1
    destination.mkdir(parents=True, exist_ok=True)
    files = public_files(source)
    for path in files:
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    exported_failures = validate(destination)
    if exported_failures:
        _print_failures(exported_failures)
        return 1
    print(f"public-export=pass files={len(files)} destination={destination}")
    return 0


def main(arguments: Sequence[str] | None = None) -> int:
    options = parser().parse_args(arguments)
    if options.export is not None:
        return export_public_tree(ROOT, options.export)
    failures = validate(ROOT)
    if failures:
        _print_failures(failures)
        return 1
    print(f"public-source-check=pass files={len(public_files(ROOT))}")
    return 0


def _print_failures(failures: Sequence[str]) -> None:
    for failure in failures:
        print(failure, file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
