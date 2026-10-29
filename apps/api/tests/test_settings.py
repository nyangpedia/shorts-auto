"""Where settings come from: config/local.settings.json beats .env beats the environment beats defaults."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.paths import find_repo_root
from app.core.settings import ENV_TO_FIELD, load_settings


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ENV_TO_FIELD:
        monkeypatch.delenv(name, raising=False)


def write(root: Path, env: str = "", local: dict | None = None) -> Path:
    if env:
        (root / ".env").write_text(env, encoding="utf-8")
    if local is not None:
        (root / "config").mkdir()
        (root / "config" / "local.settings.json").write_text(json.dumps(local), encoding="utf-8")
    return root


def test_local_file_wins_over_env_file(tmp_path: Path):
    write(tmp_path, "OPENAI_API_KEY=env-key\nBGM_VOLUME=0.10\nOUTPUT_DIR=outputs\n",
          {"openai_api_key": "local-key", "bgm_volume": 0.25, "output_dir": "custom_outputs"})
    s = load_settings(tmp_path)
    assert (s.openai_api_key, s.bgm_volume, s.output_dir) == ("local-key", 0.25, "custom_outputs")


def test_env_file_values_are_typed(tmp_path: Path):
    write(tmp_path, "YOUTUBE_API_KEY=yt-env\nWHISPER_MODEL=small\nUSE_FASTER_WHISPER=false\nBGM_VOLUME=0.3\n")
    s = load_settings(tmp_path)
    assert (s.youtube_api_key, s.whisper_model, s.use_faster_whisper, s.bgm_volume) == ("yt-env", "small", False, 0.3)


def test_defaults_and_process_env(tmp_path: Path, monkeypatch):
    s = load_settings(tmp_path)
    assert (s.openai_transcription_model, s.openai_analysis_model, s.yt_dlp_binary) == ("whisper-1", "gpt-4.1-mini", "yt-dlp")

    monkeypatch.setenv("OPENAI_ANALYSIS_MODEL", "custom-analysis")
    monkeypatch.setenv("YT_DLP_BINARY", "/usr/local/bin/yt-dlp")
    s = load_settings(tmp_path)
    assert (s.openai_analysis_model, s.yt_dlp_binary) == ("custom-analysis", "/usr/local/bin/yt-dlp")


@pytest.mark.parametrize("output_dir", ["/tmp/outputs", "../outputs", "safe/../outputs"])
def test_output_dir_stays_inside_the_repo(tmp_path: Path, output_dir: str):
    with pytest.raises(ValidationError):
        load_settings(write(tmp_path, local={"output_dir": output_dir}))


def test_repo_root_needs_its_markers(tmp_path: Path):
    with pytest.raises(RuntimeError, match="Could not find repository root"):
        find_repo_root(tmp_path)
