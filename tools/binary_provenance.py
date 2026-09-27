"""Check that frozen native binaries came from approved build inputs."""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Iterable, Sequence

NATIVE_SUFFIXES = {".dll", ".pyd", ".ocx", ".sys"}
FORBIDDEN_PATH_MARKERS = (
    ".codex",
    ".cache/codex-runtimes",
    "/poppler/",
    "/libheif/",
    "/miniconda",
    "/anaconda",
    "/mambaforge",
)


def approved_source_roots(
    project_root: str | Path,
    python_root: str | Path,
    windows_root: str | Path,
    windows_sdk_root: str | Path | None = None,
) -> tuple[Path, ...]:
    roots = [project_root, python_root, windows_root]
    if windows_sdk_root:
        roots.append(windows_sdk_root)
    return tuple(Path(root).resolve() for root in roots if root)


def native_toc_entries(entries: Iterable[Sequence[object]]) -> list[tuple[str, str]]:
    """Return native destination/source pairs from a PyInstaller TOC list."""
    result: list[tuple[str, str]] = []
    for entry in entries:
        if len(entry) < 2:
            continue
        destination, source = str(entry[0]), str(entry[1])
        if Path(destination.replace("\\", "/")).suffix.lower() not in NATIVE_SUFFIXES:
            continue
        result.append((destination, source))
    return result


def contaminated_native_sources(
    entries: Iterable[Sequence[object]], approved_roots: Sequence[Path]
) -> list[tuple[str, str]]:
    approved = tuple(Path(root).resolve() for root in approved_roots)
    contaminated: list[tuple[str, str]] = []
    for filename, raw_source in native_toc_entries(entries):
        source = Path(raw_source)
        normalized = raw_source.replace("\\", "/").lower()
        marker_match = any(marker in normalized for marker in FORBIDDEN_PATH_MARKERS)
        try:
            resolved = source.resolve(strict=True)
            within_approved_root = any(resolved.is_relative_to(root) for root in approved)
        except (OSError, RuntimeError):
            within_approved_root = False
        if marker_match or not within_approved_root:
            contaminated.append((filename, raw_source))
    return contaminated


def windows_ci_path_is_within(path: Path, root: Path) -> bool:
    """Path containment with Windows case and separator semantics."""
    path_text = os.path.normcase(os.path.abspath(str(path))).rstrip("\\/")
    root_text = os.path.normcase(os.path.abspath(str(root))).rstrip("\\/")
    return path_text == root_text or path_text.startswith(root_text + os.sep)


def read_collect_toc(path: str | Path) -> list[tuple[object, ...]]:
    """Read PyInstaller's COLLECT-00.toc without executing build metadata."""
    value = ast.literal_eval(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, tuple) or len(value) != 1 or not isinstance(value[0], list):
        raise ValueError(f"unexpected PyInstaller COLLECT TOC format: {path}")
    return value[0]
