"""Job log API (list / add / advance), mainly for tooling; the step routers log their own jobs."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.jobs.models import Command, JobState, Label, Message, Name, RelativePaths
from app.jobs.service import append_job, update_job_state
from app.projects.service import read_project


class CreateJobRequest(BaseModel):
    job_type: Name
    label: Label
    provider: Optional[Name] = None
    command: Optional[Command] = None
    input_paths: RelativePaths = Field(default_factory=list)


class UpdateJobRequest(BaseModel):
    state: JobState
    message: Message
    error_message: Optional[Message] = None
    output_paths: RelativePaths = Field(default_factory=list)


def _as_http(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail="Project not found")
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail="Job not found")
    return HTTPException(status_code=400, detail=str(exc))


def create_jobs_router(outputs_dir_provider: Callable[[], Path]) -> APIRouter:
    router = APIRouter(prefix="/api/projects/{project_id}/jobs", tags=["jobs"])
    Outputs = Depends(outputs_dir_provider)

    @router.get("")
    def get_jobs(project_id: str, outputs: Path = Outputs):
        try:
            return {"jobs": read_project(outputs, project_id).job_history}
        except (FileNotFoundError, ValueError) as exc:
            raise _as_http(exc) from exc

    @router.post("")
    def post_job(project_id: str, payload: CreateJobRequest, outputs: Path = Outputs):
        try:
            record = append_job(outputs, project_id, payload.job_type, payload.label, payload.input_paths,
                                provider=payload.provider, command=payload.command)
        except (FileNotFoundError, ValueError) as exc:
            raise _as_http(exc) from exc
        return {"job": record.model_dump()}

    @router.patch("/{job_id}")
    def patch_job(project_id: str, job_id: str, payload: UpdateJobRequest, outputs: Path = Outputs):
        try:
            record = update_job_state(outputs, project_id, job_id, payload.state, payload.message,
                                      payload.output_paths, error_message=payload.error_message)
        except (FileNotFoundError, KeyError, ValueError) as exc:
            raise _as_http(exc) from exc
        return {"job": record.model_dump()}

    return router
