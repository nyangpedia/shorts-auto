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
