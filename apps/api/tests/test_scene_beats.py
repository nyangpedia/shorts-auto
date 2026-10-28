from app.production.scenes import script_beats
from app.production.voice import slice_script_by_segments


def test_beats_are_short_and_keep_every_word():
    script = "첫째, 피라미드 하나에 쓰인 돌은 무려 230만 개 총무게만 600만 톤으로 63빌딩 12채를 합친 엄청난 스케일입니다. 놀랍죠?"
    beats = script_beats(script)
    assert " ".join(beats).split() == script.split()  # nothing dropped or reordered
    assert beats[0].startswith("첫째, ")  # the stub is folded into the next beat
    assert all(len(b) <= 30 for b in beats) and len(beats) >= 3
    assert not any(b.endswith("230만") or b.endswith("600만") for b in beats)  # numbers stay with units


def test_script_words_are_laid_over_recognised_segments():
    script = "그런데 심리학 연구에서 밝혀낸 반전이 있습니다. 첫째, 시선입니다."
    heard = [
        {"text": "그런데 심리향 연구에서", "start": 0.0, "end": 1.5},
        {"text": "밝혀는 반전이 있습니다", "start": 1.5, "end": 3.0},
        {"text": "첫째 시선입니다", "start": 3.2, "end": 4.4},
    ]
    blocks = slice_script_by_segments(script, heard)
    assert [b["text"] for b in blocks] == ["그런데 심리학 연구에서", "밝혀낸 반전이 있습니다.", "첫째, 시선입니다."]
    assert blocks[2]["start"] == 3.2


def test_rebuilding_scenes_clears_stale_scene_media(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.production import router as production_router

    monkeypatch.setattr(production_router, "generate_concept_kit_and_video_scenes", lambda path, settings, style: None)
    client = TestClient(create_app(repo_root=tmp_path))
    pid = client.post("/api/projects", json={"project_title": "t"}).json()["project"]["project_id"]
    scenes = tmp_path / "outputs" / pid / "scenes"
    scenes.mkdir(parents=True)
    for name in ("scene_01_start.png", "scene_01_video.mp4", "scene_02_final.png", "keep.txt"):
        (scenes / name).write_bytes(b"x")

    client.post(f"/api/projects/{pid}/production/concepts?style=cinematic")

    assert sorted(p.name for p in scenes.iterdir()) == ["keep.txt"]


def test_subtitle_numbers_become_digits_but_words_stay():
    from app.production.numbers import digits_for_subtitles

    assert digits_for_subtitles("초속 삼십만 킬로미터, 칠십 퍼센트") == "초속 30만km, 70%"
    assert digits_for_subtitles("구조는 이번에 만약 사실 천천히 일주일") == "구조는 이번에 만약 사실 천천히 일주일"


def test_new_sentence_is_not_stranded_at_segment_end():
    blocks = slice_script_by_segments(
        "주장이 기다립니다. 빛의 속도는 일정합니다.",
        [{"text": "주장이 기다립니다 빛의", "start": 0.0, "end": 2.0}, {"text": "속도는 일정합니다", "start": 2.0, "end": 3.0}],
    )
    assert [b["text"] for b in blocks] == ["주장이 기다립니다.", "빛의 속도는 일정합니다."]
