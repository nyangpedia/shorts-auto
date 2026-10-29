"""Bookkeeping shared by the step routers: the job log entry for a long call, and the project's
step states / generated-file index after it."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

from app.jobs.service import append_job, update_job_state
from app.projects.service import read_project, save_project

SCRIPT_FILE_KEYS = ["script_candidates", "selected_script_candidate", "final_script", "final_script_state"]
REFERENCE_FILE_KEYS = ["reference_raw_stt", "reference_script", "reference_analysis", "reference_analysis_markdown"]


class JobRun:
    def __init__(self, outputs: Path, project_id: str, job_id: str):
        self.outputs, self.project_id, self.job_id = outputs, project_id, job_id
        self.finished = False

    def note(self, message: str) -> None:
        """Update the running job's message (e.g. a second phase started)."""
        update_job_state(self.outputs, self.project_id, self.job_id, "running", message)

    def succeed(self, message: str, outputs: list[str] | None = None) -> None:
        update_job_state(self.outputs, self.project_id, self.job_id, "succeeded", message, output_paths=outputs)
        self.finished = True


@contextmanager
def job(outputs: Path, project_id: str, job_type: str, label: str, running: str, *,
        provider: str | None = None, command: str | None = None, inputs: list[str] | None = None,
        fail_on: tuple[type[BaseException], ...] = (Exception,)):
    """Log a job as running; mark it failed if the body raises one of `fail_on` (other errors pass untouched)."""
    record = append_job(outputs, project_id, job_type, label, input_paths=inputs, provider=provider, command=command)
    update_job_state(outputs, project_id, record.job_id, "running", running)
    run = JobRun(outputs, project_id, record.job_id)
    try:
        yield run
    except fail_on as exc:
        message = str(exc) or type(exc).__name__
        update_job_state(outputs, project_id, record.job_id, "failed", message, error_message=message)
        raise


def update_progress(
    outputs: Path,
    project_id: str,
    *,
    current: str | None = None,
    steps: dict[str, tuple[str, str]] | None = None,
    reset: Iterable[str] = (),
    files: dict[str, str] | None = None,
    drop_files: Iterable[str] = (),
) -> None:
    """One read-modify-write of project.json: step states, steps reset to waiting, and the file index."""
    project = read_project(outputs, project_id)
    if current:
        project.current_step = current
    reset = set(reset)
    for status in project.step_statuses:
        if steps and status.name in steps:
            status.state, status.message = steps[status.name]
        elif status.name in reset:
            status.state, status.message = "waiting", ""
    for key in drop_files:
        project.generated_files.pop(key, None)
    project.generated_files.update(files or {})
    save_project(outputs, project)
