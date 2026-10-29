"""Project folders: ids, titles, listing, and the HTTP endpoints over them."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.projects import router as projects_router
from app.projects.service import create_project, list_projects, read_project, save_project, update_project_step, update_project_title

BAD_IDS = ["../261011_2130", "261011_2130/extra", "261011_213", "2610112130", "261011_21300",
           "261011_2460", "261332_2130", "261011_21ab", "261011_.."]


# ── service ──

def test_new_project_folder(tmp_path: Path):
    project = create_project(tmp_path, project_title="테스트 쇼츠", now="261011_2130")
    assert (project.project_id, project.project_title, project.display_name) == ("261011_2130", "테스트 쇼츠", "261011_테스트 쇼츠")
    assert (tmp_path / "261011_2130" / "project.json").exists()


def test_blank_title_is_untitled(tmp_path: Path):
    project = create_project(tmp_path, project_title="   ", now="261011_2130")
    assert (project.project_title, project.display_name) == ("untitled", "261011_untitled")


def test_same_id_twice_keeps_the_first(tmp_path: Path):
    create_project(tmp_path, project_title="원본", now="261011_2130")
    with pytest.raises(FileExistsError):
        create_project(tmp_path, project_title="덮어쓰기", now="261011_2130")
    assert read_project(tmp_path, "261011_2130").project_title == "원본"


def test_rename_updates_display_name(tmp_path: Path):
    create_project(tmp_path, project_title="초기", now="261011_2130")
    assert update_project_title(tmp_path, "261011_2130", "새제목").display_name == "261011_새제목"
    assert read_project(tmp_path, "261011_2130").display_name == "261011_새제목"


@pytest.mark.parametrize("bad", BAD_IDS)
def test_malformed_ids_are_refused(tmp_path: Path, bad: str):
    for call in (lambda: read_project(tmp_path, bad),
                 lambda: update_project_title(tmp_path, bad, "새제목"),
                 lambda: create_project(tmp_path, project_title="테스트", now=bad)):
        with pytest.raises(ValueError):
            call()


def test_listing_is_newest_first_and_skips_broken_folders(tmp_path: Path):
    create_project(tmp_path, project_title="첫번째", now="261011_2130")
    create_project(tmp_path, project_title="두번째", now="261011_2140")
    (tmp_path / "261011_2150").mkdir()
    (tmp_path / "261011_2150" / "project.json").write_text("{not json", encoding="utf-8")
    tampered = create_project(tmp_path, project_title="비정상", now="261011_2200")
    data = json.loads((tmp_path / tampered.project_id / "project.json").read_text(encoding="utf-8"))
    data["project_id"] = "../261011_2200"
    (tmp_path / tampered.project_id / "project.json").write_text(json.dumps(data), encoding="utf-8")

    assert [p.project_id for p in list_projects(tmp_path)] == ["261011_2140", "261011_2130"]


def test_unknown_step_is_an_error_and_changes_nothing(tmp_path: Path):
    project = create_project(tmp_path, project_title="레퍼런스", now="261011_2130")
    project.step_statuses = [s for s in project.step_statuses if s.name != "STT"]
    save_project(tmp_path, project)

    with pytest.raises(ValueError, match="Step status not found"):
        update_project_step(tmp_path, "261011_2130", "STT", "running", "Ready")
    assert read_project(tmp_path, "261011_2130").current_step == "Reference"


def test_save_needs_an_existing_project(tmp_path: Path):
    stray = create_project(tmp_path / "elsewhere", project_title="작업", now="261011_2130")
    with pytest.raises(FileNotFoundError):
        save_project(tmp_path, stray)  # no folder here
    (tmp_path / "261011_2130").mkdir()
    with pytest.raises(FileNotFoundError):
        save_project(tmp_path, stray)  # folder, but no project.json


# ── HTTP ──

@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(repo_root=tmp_path))


def test_health(client):
    assert client.get("/api/health").json()["ok"] is True


def test_create_list_rename(client):
    pid = client.post("/api/projects", json={"project_title": "첫 프로젝트"}).json()["project"]["project_id"]
    assert client.get("/api/projects").json()["projects"][0]["project_title"] == "첫 프로젝트"
    renamed = client.patch(f"/api/projects/{pid}", json={"project_title": "변경"})
    assert renamed.json()["project"]["project_title"] == "변경"


def test_two_projects_in_the_same_minute_get_different_ids(client):
    ids = {client.post("/api/projects", json={"project_title": t}).json()["project"]["project_id"] for t in ("a", "b")}
    assert len(ids) == 2


def test_id_collision_moves_to_the_next_minute(tmp_path: Path, monkeypatch):
    tried: list[int] = []

    def fake_id(offset_minutes: int = 0) -> str:
        tried.append(offset_minutes)
        return f"260101_000{offset_minutes}"

    monkeypatch.setattr(projects_router, "timestamp_id", fake_id)
    client = TestClient(create_app(repo_root=tmp_path))
    made = [client.post("/api/projects", json={"project_title": t}).json()["project"]["project_id"] for t in ("a", "b")]
    assert made == ["260101_0000", "260101_0001"]
    assert tried == [0, 0, 1]


def test_missing_project_does_not_leak_paths(client, tmp_path: Path):
    for path in ("/api/projects/991231_2359", "/api/projects/991231_2359/jobs"):
        response = client.get(path)
        assert (response.status_code, response.json()["detail"]) == (404, "Project not found")
        assert str(tmp_path) not in response.text
