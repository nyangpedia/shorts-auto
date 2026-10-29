from pathlib import Path

from fastapi.testclient import TestClient

from app.core import usage
from app.main import create_app


def test_usage_counts_per_kind_and_reports_limits(tmp_path: Path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "local.settings.json").write_text(
        '{"llm_base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",'
        ' "llm_fallback_models": "a,b", "cloudflare_account_id": "x"}',
        encoding="utf-8",
    )
    client = TestClient(create_app(repo_root=tmp_path))
    usage.record("llm")
    usage.record("llm")
    usage.record("image")

    body = client.get("/api/usage").json()

    assert body == {"llm": 2, "llm_limit": 60, "image": 1, "image_limit": 70, "image_exhausted": False, "tts": 0}
    assert client.get("/api/projects").status_code == 200  # usage file in outputs/ must not break listing
