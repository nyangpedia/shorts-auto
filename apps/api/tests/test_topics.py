import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_topics_are_collected_and_starting_one_copies_the_analysis(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path))
    source = client.post("/api/projects", json={"project_title": "원본"}).json()["project"]["project_id"]
    src_dir = tmp_path / "outputs" / source
    (src_dir / "reference_script.md").write_text("레퍼런스 자막", encoding="utf-8")
    (src_dir / "reference_analysis.json").write_text(
        json.dumps({"recommended_topics": [{"title": "주제 하나", "hook": "훅1"}, {"title": "주제 둘", "hook": "훅2"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    topics = client.get("/api/topics").json()["topics"]
    assert [t["title"] for t in topics] == ["주제 하나", "주제 둘"]

    started = client.post(f"/api/topics/{source}/1/start").json()
    new_id = started["project"]["project_id"]
    assert started["project"]["project_title"] == "주제 둘"
    assert "2번 추천 주제로 작성: 주제 둘" == started["feedback"]
    assert (tmp_path / "outputs" / new_id / "reference_analysis.json").exists()

    after = [(t["title"], t["used_by"]) for t in client.get("/api/topics").json()["topics"]]
    assert after == [("주제 하나", None), ("주제 둘", new_id)]  # no duplicates from the copied analysis

    left = client.post("/api/topics/hide", json={"ids": [f"{source}:0"]}).json()["topics"]
    assert [t["title"] for t in left] == ["주제 둘"]
    assert client.post(f"/api/topics/{source}/0/start").status_code == 404

    body = client.post("/api/topics/restore", json={"ids": [f"{source}:0"]}).json()
    assert [t["title"] for t in body["topics"]] == ["주제 하나", "주제 둘"] and body["hidden"] == []


def test_history_shares_used_topics_and_returns_the_account_list(tmp_path):
    import json
    from fastapi.testclient import TestClient
    from app.main import create_app

    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "local.settings.json").write_text(
        '{"vite_supabase_url": "https://x.supabase.co", "vite_supabase_publishable_key": "k"}', encoding="utf-8")
    seen = {}

    def fake_sync(_settings, token, rows):
        seen.update(token=token, rows=rows)
        return [{"topic_id": "other:0", "title": "다른 PC 주제", "project_id": "p", "updated_at": "2026-10-30T01:02:03"}]

    client = TestClient(create_app(repo_root=tmp_path, member_lookup=lambda *_: {"until": None}, topic_sync=fake_sync))
    assert client.get("/api/topics/history").json() == {"items": []}  # no token, nothing shared
    body = client.get("/api/topics/history", headers={"Authorization": "Bearer t"}).json()
    assert seen["token"] == "t" and seen["rows"] == []
    assert body["items"][0]["title"] == "다른 PC 주제"
