"""Job log entries kept in project.json (job_history): what ran, when, with which inputs and outputs."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Optional
from uuid import uuid4

from pydantic import AfterValidator, BaseModel, Field

from app.projects.models import utc_now_iso

JobState = Literal["pending", "running", "succeeded", "failed"]


def _trimmed(limit: int):
    def check(value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("must not be empty")
        if len(text) > limit:
            raise ValueError(f"must be at most {limit} characters")
        return text
    return check


def _relative_paths(values: list[str]) -> list[str]:
    """File references stay inside the project folder: no absolute paths (incl. "/x" and "C:x" on Windows), no ".."."""
    for value in values:
        path = Path(value)
        if path.anchor or ".." in path.parts:
            raise ValueError("entries must be relative paths without traversal")
    return values


Name = Annotated[str, AfterValidator(_trimmed(120))]
Label = Annotated[str, AfterValidator(_trimmed(200))]
Message = Annotated[str, AfterValidator(_trimmed(2000))]
Command = Annotated[str, AfterValidator(_trimmed(500))]
RelativePaths = Annotated[list[Annotated[str, AfterValidator(_trimmed(1024))]], AfterValidator(_relative_paths)]


class JobLog(BaseModel):
    timestamp: str = Field(default_factory=utc_now_iso)
    message: Message


class JobRecord(BaseModel):
    job_id: str = Field(default_factory=lambda: uuid4().hex)
    job_type: Name
    label: Label
    provider: Optional[Name] = None
    command: Optional[Command] = None
    state: JobState = "pending"
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    error_message: Optional[Message] = None
    input_paths: RelativePaths = Field(default_factory=list)
    output_paths: RelativePaths = Field(default_factory=list)
    logs: list[JobLog] = Field(default_factory=list)
