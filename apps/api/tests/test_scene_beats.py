from app.production.service import split_into_beats


def test_beats_are_short_and_keep_every_word():
    clauses = ["첫째,", "피라미드 하나에 쓰인 돌은 무려 230만 개 총무게만 600만 톤으로 63빌딩 12채를 합친 엄청난 스케일입니다."]
    beats = split_into_beats(clauses)
    assert " ".join(beats).split() == " ".join(clauses).split()  # nothing dropped or reordered
    assert beats[0].startswith("첫째, ")  # the stub is folded into the next beat
    assert all(len(b) <= 30 for b in beats) and len(beats) >= 3
    assert not any(b.endswith("230만") or b.endswith("600만") for b in beats)  # numbers stay with units


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
