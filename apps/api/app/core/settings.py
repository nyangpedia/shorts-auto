"""App settings. Each field can come from the repo's .env as its upper-case name (GEMINI_API_KEY for
gemini_api_key); process environment variables override .env, and config/local.settings.json
overrides both."""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, field_validator

from app.core.paths import find_repo_root


class AppSettings(BaseModel):
    # keys (entered on the settings screen)
    openai_api_key: str = ""
    gemini_api_key: str = ""
    youtube_api_key: str = ""
    higgsfield_api_key: str = ""
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = ""
    # text: Gemini through its OpenAI-compatible endpoint when llm_base_url is set, otherwise OpenAI
    openai_analysis_model: str = "gpt-4.1-mini"
    llm_base_url: str = ""
    llm_fallback_models: str = ""  # comma-separated, tried in order when a model's free quota runs out
    # voice
    tts_provider: str = "gemini"  # gemini | edge
    gemini_tts_model: str = "gemini-3.8-flash-tts"
    gemini_tts_voice: str = "Kore"
    gemini_tts_style: str = "에너지 있고 또렷한 유튜브 쇼츠 내레이션"
    edge_tts_voice: str = "ko-KR-SunHiNeural"
    # speech recognition (local Whisper unless switched off)
    use_faster_whisper: bool = True
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    openai_transcription_model: str = "whisper-1"
    # pictures and sound
    visual_style: str = "claymation"
    gemini_image_model: str = "gemini-2.5-flash-image"
    bgm_path: str = "assets/bgm/channel_bgm.mp3"
    bgm_volume: float = 0.18
    # tools and storage
    yt_dlp_binary: str = "yt-dlp"
    output_dir: str = "outputs"

    @property
    def llm_fallback_list(self) -> list[str]:
        return [name.strip() for name in self.llm_fallback_models.split(",") if name.strip()]

    @property
    def llm_api_key(self) -> str:
        """The Gemini key when talking to Gemini's endpoint, otherwise the OpenAI key."""
        return self.gemini_api_key if self.llm_base_url and self.gemini_api_key else self.openai_api_key

    @field_validator("output_dir")
    @classmethod
    def _inside_repo(cls, value: str) -> str:
        path = Path(value)
        if path.anchor:  # is_absolute() misses "/tmp/x" on Windows
            raise ValueError("output_dir must be a relative path")
        if ".." in path.parts:
            raise ValueError("output_dir must not contain path traversal")
        return value


# .env / environment variable name for every setting
ENV_TO_FIELD = {name.upper(): name for name in AppSettings.model_fields}


def _from_env(repo_root: Path) -> dict[str, str]:
    raw = {**dotenv_values(repo_root / ".env"), **{k: v for k, v in os.environ.items() if k in ENV_TO_FIELD}}
    return {ENV_TO_FIELD[k]: v for k, v in raw.items() if k in ENV_TO_FIELD and v not in (None, "")}


def _from_local_file(repo_root: Path) -> dict:
    path = repo_root / "config" / "local.settings.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_settings(repo_root: Path | None = None) -> AppSettings:
    root = repo_root or find_repo_root()
    return AppSettings.model_validate({**_from_env(root), **_from_local_file(root)})
