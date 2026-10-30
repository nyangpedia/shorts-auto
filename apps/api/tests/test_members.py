from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def _client(tmp_path: Path, member, on: bool = True) -> TestClient:
    if on:
        (tmp_path / "config").mkdir(parents=True)
        (tmp_path / "config" / "local.settings.json").write_text(
            '{"vite_supabase_url": "https://x.supabase.co", "vite_supabase_publishable_key": "k"}', encoding="utf-8")
    return TestClient(create_app(repo_root=tmp_path, member_lookup=lambda _settings, _token: member))


def test_off_without_supabase_url(tmp_path: Path):
    assert _client(tmp_path, None, on=False).put("/api/settings/keys", json={}).status_code != 401


def test_reads_stay_open(tmp_path: Path):
    assert _client(tmp_path, None).get("/api/projects").status_code == 200


def test_change_needs_token(tmp_path: Path):
    assert _client(tmp_path, {"until": None}).put("/api/settings/keys", json={}).status_code == 401


def test_non_member_and_expired_are_refused(tmp_path: Path):
    headers = {"Authorization": "Bearer t"}
    assert _client(tmp_path, None).put("/api/settings/keys", json={}, headers=headers).status_code == 403
    assert _client(tmp_path / "e", {"until": "2020-01-01T00:00:00+00:00"}).put("/api/settings/keys", json={}, headers=headers).status_code == 403


def test_member_passes(tmp_path: Path):
    headers = {"Authorization": "Bearer t"}
    status = _client(tmp_path, {"until": "2999-01-01T00:00:00+00:00"}).put("/api/settings/keys", json={}, headers=headers).status_code
    assert status not in (401, 403)
