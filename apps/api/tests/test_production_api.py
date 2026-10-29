"""Production state over HTTP: scene files show up as URLs and are served with the right type."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.projects.service import create_project


def scene(n: int) -> dict:
    return {"scene_id": n, "target_duration": 5.0, "start": 5.0 * (n - 1), "end": 5.0 * n, "duration_frames": 150,
            "narration": f"{n}번 씬", "start_image_prompt": f"Prompt {n}", "video_prompt": f"Motion {n}",
            "continuity": {"camera": "Eye-level", "subject_state": "Hero", "lighting": "Studio", "handoff_description": "tilt"},
            "is_locked": False}


def test_scene_files_become_urls(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path))
    pid = create_project(tmp_path / "outputs", project_title="테스트 쇼츠", now="261016_1200").project_id
    base = f"/api/projects/{pid}/production"

    empty = client.get(base).json()
    assert empty["has_audio"] is False and empty["has_video_scenes"] is False

    folder = tmp_path / "outputs" / pid
    (folder / "video_scenes.json").write_text(json.dumps([scene(1), scene(2)]), encoding="utf-8")
    (folder / "scenes").mkdir()
    (folder / "scenes" / "scene_01_video.mp4").write_bytes(b"\x00\x00\x00\x20ftypisom")
    (folder / "scenes" / "scene_01_final.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (folder / "scenes" / "scene_02_start.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    served = client.get(f"{base}/scenes/scene_01_video.mp4")
    assert served.status_code == 200 and served.headers["content-type"] == "video/mp4"

    state = client.get(base).json()
    first, second = state["video_scenes"]
    assert state["video_scene_count"] == 2
    assert first["generated_video_url"] == f"{base}/scenes/scene_01_video.mp4"
    assert first["final_frame_url"] == f"{base}/scenes/scene_01_final.png"
    assert second["start_image_url"] == f"{base}/scenes/scene_02_start.png"
    assert second["continuity"]["prev_final_frame_url"] == first["final_frame_url"]


def test_only_scene_files_are_served(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path))
    pid = create_project(tmp_path / "outputs", project_title="t", now="261016_1200").project_id
    (tmp_path / "outputs" / pid / "scenes").mkdir()
    (tmp_path / "outputs" / pid / "scenes" / "notes.txt").write_text("x", encoding="utf-8")
    assert client.get(f"/api/projects/{pid}/production/scenes/notes.txt").status_code in (400, 404)


def test_thumbnail_from_a_scene_picture(tmp_path: Path):
    from PIL import Image

    client = TestClient(create_app(repo_root=tmp_path))
    pid = create_project(tmp_path / "outputs", project_title="t", now="261016_1200").project_id
    base = f"/api/projects/{pid}/production"
    assert client.post(f"{base}/thumbnail", json={"scene_id": 1, "title": "제목"}).status_code == 400  # no picture yet

    (tmp_path / "outputs" / pid / "scenes").mkdir(exist_ok=True)  # scene_asset may have made it
    Image.new("RGB", (768, 1344), (40, 80, 120)).save(tmp_path / "outputs" / pid / "scenes" / "scene_01_start.png")
    made = client.post(f"{base}/thumbnail", json={"scene_id": 1, "title": "아주 긴 제목이 들어가도 세 줄 안에 맞춰집니다 정말로"})
    assert made.json()["thumbnail_url"] == f"{base}/thumbnail"
    assert client.get(base).json()["thumbnail_url"] == f"{base}/thumbnail"
    image = Image.open(tmp_path / "outputs" / pid / "thumbnail.jpg")
    assert image.size == (1080, 1920)
