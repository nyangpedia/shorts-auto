"""Job records in project.json: lifecycle, validation, and the jobs endpoints."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.jobs.models import JobLog, JobRecord
from app.jobs.service import append_job, update_job_state
from app.main import create_app
from app.projects.service import create_project, read_project, save_project

PID = "261011_2130"


@pytest.fixture
def outputs(tmp_path: Path) -> Path:
    create_project(tmp_path, project_title="작업", now=PID)
    return tmp_path


def new_job(outputs: Path, **extra) -> JobRecord:
    return append_job(outputs, PID, job_type="reference_search", label="Reference search", **extra)


# ── service ──

def test_new_job_is_pending(outputs):
    job = new_job(outputs, provider="youtube", command="search references")
    assert job.job_id and job.state == "pending"
    assert (job.provider, job.command) == ("youtube", "search references")
    assert job.started_at is job.ended_at is job.error_message is None
    assert read_project(outputs, PID).job_history[0]["job_type"] == "reference_search"


def test_lifecycle_timestamps_and_logs(outputs):
    job = new_job(outputs)
    running = update_job_state(outputs, PID, job.job_id, state="running", message="Started")
    assert running.started_at is not None and running.ended_at is None

    failed = update_job_state(outputs, PID, job.job_id, state="failed", message="Missing key", error_message="YouTube API key missing")
    assert failed.started_at == running.started_at and failed.ended_at is not None
    assert (failed.error_message, failed.logs[-1].message) == ("YouTube API key missing", "Missing key")


def test_finished_job_is_saved_with_outputs(outputs):
    job = new_job(outputs)
    update_job_state(outputs, PID, job.job_id, state="succeeded", message="References saved", output_paths=["references/items.json"])
    saved = JobRecord.model_validate(read_project(outputs, PID).job_history[0])
    assert (saved.state, saved.logs[-1].message, saved.output_paths) == ("succeeded", "References saved", ["references/items.json"])
    assert saved.ended_at is not None


def test_unknown_job(outputs):
    with pytest.raises(KeyError):
        update_job_state(outputs, PID, "missing-job", state="failed", message="x")


def test_duplicated_job_id_is_an_error(outputs):
    job = new_job(outputs)
    project = read_project(outputs, PID)
    project.job_history.append(dict(project.job_history[0]))
    save_project(outputs, project)
    with pytest.raises(ValueError):
        update_job_state(outputs, PID, job.job_id, state="failed", message="x")


@pytest.mark.parametrize("field", ["job_type", "label"])
def test_required_text(field):
    with pytest.raises(ValidationError):
        JobRecord(**{"job_type": "reference_search", "label": "Reference search", field: "   "})
    with pytest.raises(ValidationError):
        JobLog(message="   ")


@pytest.mark.parametrize("path", ["/tmp/out.mp4", "../secret.txt", "outputs/../secret.txt"])
def test_paths_stay_inside_the_project(path):
    with pytest.raises(ValidationError):
        JobRecord(job_type="script", label="Script", input_paths=[path])


# ── HTTP ──

@pytest.fixture
def api(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path))
    pid = client.post("/api/projects", json={"project_title": "작업 프로젝트"}).json()["project"]["project_id"]
    return client, f"/api/projects/{pid}/jobs"


def test_create_finish_list(api):
    client, jobs = api
    assert client.get(jobs).json()["jobs"] == []

    created = client.post(jobs, json={"job_type": "script", "label": "대본 생성", "provider": "openai",
                                      "command": "generate script", "input_paths": ["inputs/topic.txt"]}).json()["job"]
    assert (created["job_type"], created["provider"], created["command"]) == ("script", "openai", "generate script")
    assert created["started_at"] is created["ended_at"] is None

    done = client.patch(f"{jobs}/{created['job_id']}", json={"state": "succeeded", "message": "완료", "output_paths": ["outputs/script.md"]}).json()["job"]
    assert done["state"] == "succeeded" and done["ended_at"] is not None and done["logs"][0]["message"] == "완료"
    assert client.get(jobs).json()["jobs"][0]["job_id"] == created["job_id"]


def test_unknown_job_does_not_leak_paths(api, tmp_path: Path):
    client, jobs = api
    response = client.patch(f"{jobs}/missing-job", json={"state": "failed", "message": "실패"})
    assert (response.status_code, response.json()["detail"]) == (404, "Job not found")
    assert str(tmp_path) not in response.text


@pytest.mark.parametrize("create,patch", [
    ({"job_type": " ", "label": "", "input_paths": ["inputs/topic.txt", " "]}, {"state": "succeeded", "message": " ", "output_paths": [" "]}),
    ({"job_type": "script", "label": "대본 생성", "input_paths": ["../secret.txt"]}, {"state": "succeeded", "message": "완료", "output_paths": ["/tmp/out.mp4"]}),
])
def test_bad_payloads_are_422(api, create, patch):
    client, jobs = api
    assert client.post(jobs, json=create).status_code == 422
    assert client.patch(f"{jobs}/anything", json=patch).status_code == 422
