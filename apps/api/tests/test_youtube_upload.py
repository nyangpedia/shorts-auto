import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.main import create_app
from app.uploads.router import parse_tags


def test_parse_tags():
    assert parse_tags("#a #b, c") == ["a", "b", "c"]
    assert len(parse_tags(" ".join(f"t{i}" for i in range(40)))) == 15


def test_upload_goes_up_private_and_records_video_id(tmp_path: Path):
    (tmp_path / "client_secret.json").write_text(json.dumps({"installed": {
        "client_id": "id", "client_secret": "s", "token_uri": "https://oauth/token", "auth_uri": "https://oauth/auth"}}))
    (tmp_path / ".youtube_token.json").write_text(json.dumps({"refresh_token": "r"}))
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth":
            return httpx.Response(200, json={"access_token": "at"})
        if request.method == "POST":
            seen["meta"] = json.loads(request.content)
            return httpx.Response(200, headers={"location": "https://upload.example/session"})
        return httpx.Response(200, json={"id": "vid123"})

    client = TestClient(create_app(repo_root=tmp_path, upload_transport=httpx.MockTransport(handler)))
    project_id = client.post("/api/projects", json={"project_title": "업로드"}).json()["project"]["project_id"]

    no_video = client.post(f"/api/projects/{project_id}/youtube/upload", json={"title": "t"})
    assert no_video.status_code == 400

    (tmp_path / "outputs" / project_id / "final.mp4").write_bytes(b"video")
    response = client.post(f"/api/projects/{project_id}/youtube/upload", json={"title": "제목", "description": "설명", "tags": "#a #b"})
    assert response.status_code == 200, response.text
    assert response.json()["video_id"] == "vid123"
    assert seen["meta"]["status"]["privacyStatus"] == "private"
    assert seen["meta"]["snippet"]["tags"] == ["a", "b"] and seen["meta"]["snippet"]["description"].endswith("#Shorts")
    saved = client.get(f"/api/projects/{project_id}").json()["project"]
    assert saved["generated_files"]["youtube_video"] == "vid123"
