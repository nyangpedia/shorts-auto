from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.paths import find_repo_root
from app.core.settings import ENV_TO_FIELD, load_settings


def clear_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ENV_TO_FIELD:
        monkeypatch.delenv(key, raising=False)


def test_local_settings_override_env(tmp_path: Path, monkeypatch):
    clear_settings_env(monkeypatch)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text(
        '{"openai_api_key":"local-key","bgm_volume":0.25,"output_dir":"custom_outputs"}',
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=env-key\nBGM_VOLUME=0.10\nOUTPUT_DIR=outputs\n",
        encoding="utf-8",
    )

    settings = load_settings(tmp_path)

    assert settings.openai_api_key == "local-key"
    assert settings.bgm_volume == 0.25
    assert settings.output_dir == "custom_outputs"


def test_env_used_when_local_settings_missing(tmp_path: Path, monkeypatch):
    clear_settings_env(monkeypatch)
    (tmp_path / ".env").write_text(
        "YOUTUBE_API_KEY=yt-env\nWHISPER_MODEL=small\nUSE_FASTER_WHISPER=false\nBGM_VOLUME=0.3\n",
        encoding="utf-8",
    )

    settings = load_settings(tmp_path)

    assert settings.youtube_api_key == "yt-env"
    assert settings.whisper_model == "small"
    assert settings.use_faster_whisper is False and settings.bgm_volume == 0.3  # text from .env is typed


def test_reference_phase_settings_have_safe_defaults(tmp_path, monkeypatch):
    clear_settings_env(monkeypatch)

    settings = load_settings(tmp_path)

    assert settings.openai_transcription_model == "whisper-1"
    assert settings.openai_analysis_model == "gpt-4.1-mini"
    assert settings.yt_dlp_binary == "yt-dlp"


def test_reference_phase_env_overrides(monkeypatch, tmp_path):
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("OPENAI_TRANSCRIPTION_MODEL", "custom-transcribe")
    monkeypatch.setenv("OPENAI_ANALYSIS_MODEL", "custom-analysis")
    monkeypatch.setenv("YT_DLP_BINARY", "/usr/local/bin/yt-dlp")

    settings = load_settings(tmp_path)

    assert settings.openai_transcription_model == "custom-transcribe"
    assert settings.openai_analysis_model == "custom-analysis"
    assert settings.yt_dlp_binary == "/usr/local/bin/yt-dlp"


@pytest.mark.parametrize("output_dir", ["/tmp/outputs", "../outputs", "safe/../outputs"])
def test_output_dir_rejects_absolute_and_traversal(
    tmp_path: Path, monkeypatch, output_dir: str
):
    clear_settings_env(monkeypatch)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text(
        f'{{"output_dir":"{output_dir}"}}',
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_settings(tmp_path)


def test_find_repo_root_raises_when_markers_are_missing(tmp_path: Path):
    with pytest.raises(RuntimeError, match="Could not find repository root"):
        find_repo_root(tmp_path)
