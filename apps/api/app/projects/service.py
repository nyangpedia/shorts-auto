"""Project folders: create, read, list, rename, archive, delete. Ids are YYMMDD_HHMM timestamps, which
also keeps any id from escaping the outputs folder."""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from app.core.storage import write_text_atomic
from app.projects.models import Project, StepName, StepState, default_step_statuses, utc_now_iso

_ID_SHAPE = re.compile(r"^\d{6}_\d{4}$")
PROJECT_FILE = "project.json"


def _checked_id(project_id: str) -> str:
    if not _ID_SHAPE.fullmatch(project_id):
        raise ValueError("project_id must match YYMMDD_HHMM")
    try:
        datetime.strptime(project_id, "%y%m%d_%H%M")
    except ValueError as exc:
        raise ValueError("project_id must be a valid YYMMDD_HHMM timestamp") from exc
    return project_id


def _project_path(outputs_dir: Path, project_id: str) -> Path:
    folder = (outputs_dir / _checked_id(project_id)).resolve()
    if not folder.is_relative_to(outputs_dir.resolve()):
        raise ValueError("project path must stay under outputs_dir")
    return folder


def _display_name(project_id: str, title: str) -> str:
    return f"{project_id.split('_')[0]}_{title.strip() or 'untitled'}"


def _store(outputs_dir: Path, project: Project, *, new: bool = False) -> None:
    folder = _project_path(outputs_dir, project.project_id)
    if new:
        folder.mkdir(parents=True, exist_ok=False)  # FileExistsError: that minute is taken, try the next
    elif not (folder / PROJECT_FILE).is_file():
        raise FileNotFoundError(f"Project does not exist: {project.project_id}")
    write_text_atomic(folder / PROJECT_FILE, json.dumps(project.model_dump(), ensure_ascii=False, indent=2))


def save_project(outputs_dir: Path, project: Project) -> None:
    _store(outputs_dir, project)


def create_project(outputs_dir: Path, project_title: str, now: str) -> Project:
    created = utc_now_iso()
    title = project_title.strip() or "untitled"
    project = Project(
        project_id=_checked_id(now), project_title=title, display_name=_display_name(now, title),
        created_at=created, updated_at=created, step_statuses=default_step_statuses(),
    )
    _store(outputs_dir, project, new=True)
    return project


def read_project(outputs_dir: Path, project_id: str) -> Project:
    data = (_project_path(outputs_dir, project_id) / PROJECT_FILE).read_text(encoding="utf-8")
    return Project.model_validate(json.loads(data))


def list_projects(outputs_dir: Path) -> list[Project]:
    """Newest first; folders that aren't valid projects (caches, half-written copies) are skipped."""
    found: list[Project] = []
    for path in outputs_dir.glob(f"*/{PROJECT_FILE}") if outputs_dir.exists() else []:
        try:
            project = Project.model_validate_json(path.read_text(encoding="utf-8"))
            _checked_id(project.project_id)
        except (ValidationError, ValueError):
            continue
        found.append(project)
    return sorted(found, key=lambda p: p.project_id, reverse=True)


def _edit(outputs_dir: Path, project_id: str, change) -> Project:
    project = read_project(outputs_dir, project_id)
    change(project)
    project.updated_at = utc_now_iso()
    _store(outputs_dir, project)
    return project


def update_project_title(outputs_dir: Path, project_id: str, project_title: str) -> Project:
    def rename(p: Project) -> None:
        p.project_title = project_title.strip() or "untitled"
        p.display_name = _display_name(p.project_id, p.project_title)
    return _edit(outputs_dir, project_id, rename)


def set_project_archived(outputs_dir: Path, project_id: str, archived: bool) -> Project:
    return _edit(outputs_dir, project_id, lambda p: setattr(p, "archived", archived))


def delete_project(outputs_dir: Path, project_id: str) -> None:
    read_project(outputs_dir, project_id)  # unknown ids fail before anything is removed
    shutil.rmtree(_project_path(outputs_dir, project_id))


def update_project_step(outputs_dir: Path, project_id: str, step_name: StepName, state: StepState, message: str) -> Project:
    def move(p: Project) -> None:
        step = next((s for s in p.step_statuses if s.name == step_name), None)
        if step is None:
            raise ValueError(f"Step status not found: {step_name}")
        p.current_step = step_name
        step.state, step.message = state, message
    return _edit(outputs_dir, project_id, move)
