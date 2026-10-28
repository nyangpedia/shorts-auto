from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.references.models import ReferenceCandidate
from app.references.router import add_korean_titles


def test_archive_then_delete_project(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path))
    project_id = client.post("/api/projects", json={"project_title": "보관"}).json()["project"]["project_id"]

    archived = client.patch(f"/api/projects/{project_id}", json={"archived": True}).json()["project"]
    assert archived["archived"] is True and archived["project_title"] == "보관"

    assert client.delete(f"/api/projects/{project_id}").status_code == 200
    assert client.get(f"/api/projects/{project_id}").status_code == 404
    assert client.delete("/api/projects/..").status_code in (400, 404)


def _candidate(video_id: str, title: str) -> ReferenceCandidate:
    return ReferenceCandidate(
        video_id=video_id, url=f"https://youtu.be/{video_id}", title=title, channel_id="c", channel_name="ch",
        thumbnail_url="https://i.ytimg.com/x.jpg", upload_date="2026-10-01", duration_seconds=30,
        view_count=10, source_type="search",
    )


class _Translator:
    def __init__(self, titles):
        self.titles = titles

    def analyze(self, prompt: str) -> dict:
        return {"titles": self.titles}


def test_korean_titles_only_gloss_foreign_titles():
    items = [_candidate("a", "돈 버는 습관"), _candidate("b", "賢い人ほど謝る")]
    glossed = add_korean_titles(items, lambda: _Translator(["똑똑한 사람일수록 사과한다"]))
    assert [c.title_ko for c in glossed] == [None, "똑똑한 사람일수록 사과한다"]
    # a broken or mismatched reply leaves the search results untouched
    assert add_korean_titles(items, lambda: _Translator([])) == items


def test_same_search_same_day_survives_restart(tmp_path: Path):
    calls = []

    class FakeYouTube:
        def __init__(self, key):
            pass

        def search(self, request):
            calls.append(request.keyword)
            return [_candidate("a", "돈 버는 습관")]

    body = {"keyword": "돈 습관"}
    first = TestClient(create_app(repo_root=tmp_path, youtube_client_factory=FakeYouTube))
    pid = first.post("/api/projects", json={"project_title": "x"}).json()["project"]["project_id"]
    first.post(f"/api/projects/{pid}/reference/search", json=body)

    restarted = TestClient(create_app(repo_root=tmp_path, youtube_client_factory=FakeYouTube))
    other = restarted.post("/api/projects", json={"project_title": "y"}).json()["project"]["project_id"]
    again = restarted.post(f"/api/projects/{other}/reference/search", json=body).json()
    assert calls == ["돈 습관"] and [c["video_id"] for c in again["candidates"]] == ["a"]
