"""Adding and advancing job log entries in a project's job_history."""
from __future__ import annotations

from pathlib import Path

from app.jobs.models import JobLog, JobRecord, JobState
from app.projects.models import utc_now_iso
from app.projects.service import read_project, save_project


def append_job(
    outputs_dir: Path,
    project_id: str,
    job_type: str,
    label: str,
    input_paths: list[str] | None = None,
    provider: str | None = None,
    command: str | None = None,
) -> JobRecord:
    project = read_project(outputs_dir, project_id)
    record = JobRecord(job_type=job_type, label=label, input_paths=input_paths or [], provider=provider, command=command)
    project.job_history.append(record.model_dump())
    project.updated_at = utc_now_iso()
    save_project(outputs_dir, project)
    return record


def update_job_state(
    outputs_dir: Path,
    project_id: str,
    job_id: str,
    state: JobState,
    message: str,
    output_paths: list[str] | None = None,
    error_message: str | None = None,
) -> JobRecord:
    """Move a job to `state` and log `message`; KeyError if unknown, ValueError if the id is duplicated."""
    project = read_project(outputs_dir, project_id)
    positions = [i for i, raw in enumerate(project.job_history) if raw.get("job_id") == job_id]
    if not positions:
        raise KeyError(f"Job not found: {job_id}")
    if len(positions) > 1:
        raise ValueError(f"Duplicate job_id found: {job_id}")

    record = JobRecord.model_validate(project.job_history[positions[0]])
    now = utc_now_iso()
    record.state = state
    record.updated_at = now
    if state == "running":
        record.started_at = record.started_at or now
    if state in ("succeeded", "failed"):
        record.ended_at = now
    if state == "failed":
        record.error_message = error_message or message
    elif error_message is not None:
        record.error_message = error_message
    record.logs.append(JobLog(message=message))
    record.output_paths.extend(output_paths or [])
    record = JobRecord.model_validate(record.model_dump())  # re-check the appended paths/messages

    project.job_history[positions[0]] = record.model_dump()
    project.updated_at = now
    save_project(outputs_dir, project)
    return record
