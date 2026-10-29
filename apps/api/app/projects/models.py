"""A project: one Short in the making, stored as outputs/<YYMMDD_HHMM>/project.json."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

StepName = Literal["Reference", "STT", "Analysis", "Candidates", "Script", "Production", "Render"]
StepState = Literal["waiting", "running", "succeeded", "failed"]
# The pipeline in order; the UI's six steps group these.
WORKFLOW_STEPS: list[StepName] = ["Reference", "STT", "Analysis", "Candidates", "Script", "Production", "Render"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StepStatus(BaseModel):
    name: StepName
    state: StepState = "waiting"
    message: str = ""


def default_step_statuses() -> list[StepStatus]:
    """A new project starts on the reference step; everything after it waits."""
    return [StepStatus(name=name, state="running" if name == "Reference" else "waiting") for name in WORKFLOW_STEPS]


class Project(BaseModel):
    project_id: str
    project_title: str
    display_name: str  # "YYMMDD_title", shown in lists
    created_at: str
    updated_at: str
    current_step: StepName = "Reference"
    step_statuses: list[StepStatus] = Field(default_factory=list)
    selected_reference_path: Optional[str] = None
    selected_candidate_id: Optional[str] = None
    settings_snapshot: dict = Field(default_factory=dict)
    job_history: list[dict] = Field(default_factory=list)
    generated_files: dict[str, str] = Field(default_factory=dict)  # logical name → file in the project folder
    archived: bool = False
