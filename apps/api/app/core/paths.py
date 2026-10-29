from __future__ import annotations

from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    """The monorepo root: the nearest folder above `start` holding package.json plus the workspace file or apps/."""
    here = (start or Path(__file__)).resolve()
    for folder in (here, *here.parents):
        is_workspace = (folder / "pnpm-workspace.yaml").exists() or (folder / "apps").exists()
        if (folder / "package.json").exists() and is_workspace:
            return folder
    raise RuntimeError("Could not find repository root")
