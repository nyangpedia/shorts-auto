import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_keys_are_saved_to_env_and_never_echoed(tmp_path: Path, monkeypatch):
    for env in ("GEMINI_API_KEY", "OPENAI_API_KEY", "LLM_BASE_URL", "YOUTUBE_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    client = TestClient(create_app(repo_root=tmp_path))
    assert client.get("/api/settings/keys").json()["keys"]["GEMINI_API_KEY"] is False

    body = client.put("/api/settings/keys", json={"values": {"GEMINI_API_KEY": "g-secret", "YOUTUBE_API_KEY": "y-secret"}})
    assert body.status_code == 200 and "secret" not in body.text
    assert body.json()["keys"]["GEMINI_API_KEY"] is True
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "GEMINI_API_KEY=g-secret" in env and "LLM_BASE_URL=https://generativelanguage" in env  # gemini-only install

    client.put("/api/settings/keys", json={"values": {"YOUTUBE_API_KEY": ""}})
    assert "YOUTUBE_API_KEY" not in (tmp_path / ".env").read_text(encoding="utf-8")
    assert client.put("/api/settings/keys", json={"values": {"OUTPUT_DIR": "x"}}).status_code == 400
    assert client.put("/api/settings/keys", json={"values": {"GEMINI_API_KEY": "a\nOUTPUT_DIR=/x"}}).status_code == 400


def test_client_secret_upload_requires_desktop_client(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path))
    cfg = {"client_id": "i", "client_secret": "s", "auth_uri": "https://a", "token_uri": "https://t"}
    assert client.put("/api/youtube/client-secret", json={"content": "not json"}).status_code == 400
    assert client.put("/api/youtube/client-secret", json={"content": json.dumps({"web": cfg})}).status_code == 400
    ok = client.put("/api/youtube/client-secret", json={"content": json.dumps({"installed": cfg})})
    assert ok.json() == {"configured": True, "connected": False}
