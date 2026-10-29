"""Project list / create / open / rename-archive / delete API."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.projects.service import create_project, delete_project, list_projects, read_project, set_project_archived, update_project_title

# A new project takes the current minute as its id; if taken, the next free minute within a day.
MAX_PROJECT_ID_ATTEMPTS = 24 * 60


def timestamp_id(offset_minutes: int = 0) -> str:
    return (datetime.now() + timedelta(minutes=offset_minutes)).strftime("%y%m%d_%H%M")


class CreateProjectRequest(BaseModel):
    project_title: str = "untitled"


class UpdateProjectRequest(BaseModel):
    project_title: Optional[str] = None
    archived: Optional[bool] = None


def _as_http(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail="Project not found")
    return HTTPException(status_code=400, detail=str(exc))


def create_projects_router(outputs_dir_provider: Callable[[], Path]) -> APIRouter:
    router = APIRouter(prefix="/api/projects", tags=["projects"])
    Outputs = Depends(outputs_dir_provider)

    @router.get("")
    def get_projects(outputs: Path = Outputs):
        return {"projects": [p.model_dump() for p in list_projects(outputs)]}

    @router.post("")
    def post_project(payload: CreateProjectRequest, outputs: Path = Outputs):
        for offset in range(MAX_PROJECT_ID_ATTEMPTS):
            try:
                return {"project": create_project(outputs, payload.project_title, timestamp_id(offset)).model_dump()}
            except FileExistsError:
                continue
            except ValueError as exc:
                raise _as_http(exc) from exc
        raise HTTPException(status_code=409, detail="Could not allocate a unique project_id")

    @router.get("/{project_id}")
    def get_project(project_id: str, outputs: Path = Outputs):
        try:
            return {"project": read_project(outputs, project_id).model_dump()}
        except (FileNotFoundError, ValueError) as exc:
            raise _as_http(exc) from exc

    @router.patch("/{project_id}")
    def patch_project(project_id: str, payload: UpdateProjectRequest, outputs: Path = Outputs):
        try:
            project = read_project(outputs, project_id)
            if payload.project_title is not None:
                project = update_project_title(outputs, project_id, payload.project_title)
            if payload.archived is not None:
                project = set_project_archived(outputs, project_id, payload.archived)
        except (FileNotFoundError, ValueError) as exc:
            raise _as_http(exc) from exc
        return {"project": project.model_dump()}

    @router.delete("/{project_id}")
    def remove_project(project_id: str, outputs: Path = Outputs):
        try:
            delete_project(outputs, project_id)
        except (FileNotFoundError, ValueError) as exc:
            raise _as_http(exc) from exc
        return {"deleted": project_id}

    return router
