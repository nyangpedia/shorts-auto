"""Crash-safe file writes: write to a temp file beside the target, flush to disk, then swap it in.

A half-written project file (power cut, killed server) would otherwise break the project on reload.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def write_text_atomic(path: Path, text: str) -> None:
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def write_json_atomic(path: Path, data: object) -> None:
    write_text_atomic(path, json.dumps(data, ensure_ascii=False, indent=2))


def write_many_atomic(files: dict[Path, str]) -> None:
    """Swap several files in only after all of them were written (analysis JSON + its report)."""
    staged: list[tuple[str, Path]] = []
    try:
        for path, text in files.items():
            fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
            staged.append((temp_name, path))
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
        for temp_name, path in staged:
            os.replace(temp_name, path)
    finally:
        for temp_name, _ in staged:
            if os.path.exists(temp_name):
                os.unlink(temp_name)


def remove_files(folder: Path, names: list[str]) -> None:
    for name in names:
        (folder / name).unlink(missing_ok=True)
