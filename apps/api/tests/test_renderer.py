import json
from pathlib import Path

from app.production.renderer import opening_title, subtitle_blocks


def test_subtitles_come_from_scene_blocks_then_raw_recognition(tmp_path: Path):
    (tmp_path / "raw_stt.json").write_text(json.dumps([{"start": 0, "end": 1, "text": "인식 결과"}]), encoding="utf-8")
    assert [b["text"] for b in subtitle_blocks(tmp_path)] == ["인식 결과"]

    (tmp_path / "scene_data.json").write_text(json.dumps([
        {"scene_id": 1, "start": 0, "end": 3, "text_blocks": [{"start": 0, "end": 1.5, "text": "대본 첫 줄"}, {"start": 1.5, "end": 3, "text": " "}]},
    ]), encoding="utf-8")
    assert subtitle_blocks(tmp_path) == [{"start": 0.0, "end": 1.5, "text": "대본 첫 줄"}]


def test_opening_title_never_uses_the_untitled_placeholder(tmp_path: Path):
    (tmp_path / "project.json").write_text(json.dumps({"project_title": "untitled"}), encoding="utf-8")
    assert opening_title(tmp_path, None) is None
    assert opening_title(tmp_path, "  지구의 비밀 ") == "지구의 비밀"
    (tmp_path / "project.json").write_text(json.dumps({"project_title": "피라미드"}), encoding="utf-8")
    assert opening_title(tmp_path, "") == "피라미드"


def test_scene_files_are_served_only_by_their_own_names(tmp_path: Path):
    from fastapi.testclient import TestClient
    from app.main import create_app

    client = TestClient(create_app(repo_root=tmp_path))
    pid = client.post("/api/projects", json={"project_title": "t"}).json()["project"]["project_id"]
    scenes = tmp_path / "outputs" / pid / "scenes"
    scenes.mkdir(parents=True)
    (scenes / "scene_01_start.png").write_bytes(b"png")
    (scenes / "notes.txt").write_bytes(b"x")

    assert client.get(f"/api/projects/{pid}/production/scenes/scene_01_start.png").status_code == 200
    assert client.get(f"/api/projects/{pid}/production/scenes/notes.txt").status_code == 404
    assert client.get(f"/api/projects/{pid}/production/scenes/..%2Fproject.json").status_code == 404


def test_composition_folder_for_hyperframes(tmp_path, monkeypatch):
    from app.core.paths import find_repo_root
    from app.production import renderer

    monkeypatch.setattr(renderer, "media_duration", lambda path: 20.0)  # the music file is 20 s
    for name in ("track.mp4", "voice.wav", "bgm.mp3"):
        (tmp_path / name).write_bytes(b"x")
    props = {"fps": 24, "durationInFrames": 24 * 50, "voice": "voice.wav", "bgm": "bgm.mp3", "bgmVolume": 0.15,
             "subtitles": [{"text": "</script><b>깨지지 않음", "start": 0, "end": 1}], "title": "제목", "sceneStarts": [2.5]}
    folder = renderer.build_composition(props, {n: tmp_path / n for n in ("track.mp4", "voice.wav", "bgm.mp3")},
                                        tmp_path / "comp", find_repo_root() / "apps" / "video")

    html = (folder / "index.html").read_text(encoding="utf-8")
    assert "__" not in html.replace("__timelines", "")  # every placeholder filled
    assert 'data-duration="50.000"' in html and 'data-fps="24"' in html
    assert html.count('src="assets/bgm.mp3"') == 3  # 50 s of video, 20 s of music: looped 3 times
    assert "</script><b>" not in html  # a subtitle can't end the script early
    assert (folder / "assets" / "track.mp4").exists() and (folder / "Pretendard-Black.woff2").exists()
