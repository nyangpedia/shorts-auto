from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from pydantic import BaseModel, Field, field_validator

from app.core.paths import find_repo_root


class SubtitleStyle(BaseModel):
    font_family: str = "system"
    font_weight: int = 800
    text_color: str = "#FFFFFF"
    outline_color: str = "#111111"
    position: str = "bottom-center"


class AppSettings(BaseModel):
    openai_api_key: str = ""
    gemini_api_key: str = ""
    youtube_api_key: str = ""
    higgsfield_api_key: str = ""
    pexels_api_key: str = ""
    pixabay_api_key: str = ""
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = ""
    qwen3_tts_base_url: str = "http://127.0.0.1:7860"
    tts_provider: str = "gemini"
    visual_style: str = "claymation"
    gemini_image_model: str = "gemini-2.5-flash-image"
    gemini_tts_model: str = "gemini-3.8-flash-tts"
    gemini_tts_voice: str = "Kore"
    gemini_tts_style: str = "에너지 있고 또렷한 유튜브 쇼츠 내레이션"
    edge_tts_voice: str = "ko-KR-SunHiNeural"
    reference_voice_path: str = "assets/reference_voice/reference_voice.mp3"
    reference_voice_text: str = (
        "안녕하세요 여러분. 반갑습니다. 오늘도 저희 채널을 찾아주셔서 감사합니다. "
        "영상이 도움되셨다면 구독과 좋아요를 눌러주세요."
    )
    bgm_path: str = "assets/bgm/channel_bgm.mp3"
    bgm_volume: float = 0.18
    output_dir: str = "outputs"
    default_shorts_duration_seconds: int = 45
    openai_transcription_model: str = "whisper-1"
    openai_analysis_model: str = "gpt-4.1-mini"
    llm_base_url: str = ""
    llm_fallback_models: str = ""
    yt_dlp_binary: str = "yt-dlp"
    reference_audio_filename: str = "reference_audio.wav"
    use_faster_whisper: bool = True
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    subtitle_style: SubtitleStyle = Field(default_factory=SubtitleStyle)

    @property
    def llm_fallback_list(self) -> list[str]:
        return [m.strip() for m in self.llm_fallback_models.split(",") if m.strip()]

    @property
    def llm_api_key(self) -> str:
        return self.gemini_api_key if self.llm_base_url and self.gemini_api_key else self.openai_api_key

    @field_validator("output_dir")
    @classmethod
    def validate_output_dir(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute():
            raise ValueError("output_dir must be a relative path")
        if ".." in path.parts:
            raise ValueError("output_dir must not contain path traversal")
        return value


ENV_TO_FIELD = {
    "OPENAI_API_KEY": "openai_api_key",
    "GEMINI_API_KEY": "gemini_api_key",
    "YOUTUBE_API_KEY": "youtube_api_key",
    "HIGGSFIELD_API_KEY": "higgsfield_api_key",
    "PEXELS_API_KEY": "pexels_api_key",
    "PIXABAY_API_KEY": "pixabay_api_key",
    "CLOUDFLARE_ACCOUNT_ID": "cloudflare_account_id",
    "CLOUDFLARE_API_TOKEN": "cloudflare_api_token",
    "QWEN3_TTS_BASE_URL": "qwen3_tts_base_url",
    "TTS_PROVIDER": "tts_provider",
    "VISUAL_STYLE": "visual_style",
    "GEMINI_IMAGE_MODEL": "gemini_image_model",
    "GEMINI_TTS_MODEL": "gemini_tts_model",
    "GEMINI_TTS_VOICE": "gemini_tts_voice",
    "GEMINI_TTS_STYLE": "gemini_tts_style",
    "EDGE_TTS_VOICE": "edge_tts_voice",
    "REFERENCE_VOICE_PATH": "reference_voice_path",
    "REFERENCE_VOICE_TEXT": "reference_voice_text",
    "BGM_PATH": "bgm_path",
    "BGM_VOLUME": "bgm_volume",
    "OUTPUT_DIR": "output_dir",
    "DEFAULT_SHORTS_DURATION_SECONDS": "default_shorts_duration_seconds",
    "OPENAI_TRANSCRIPTION_MODEL": "openai_transcription_model",
    "OPENAI_ANALYSIS_MODEL": "openai_analysis_model",
    "LLM_BASE_URL": "llm_base_url",
    "LLM_FALLBACK_MODELS": "llm_fallback_models",
    "YT_DLP_BINARY": "yt_dlp_binary",
    "REFERENCE_AUDIO_FILENAME": "reference_audio_filename",
    "USE_FASTER_WHISPER": "use_faster_whisper",
    "WHISPER_MODEL": "whisper_model",
    "WHISPER_DEVICE": "whisper_device",
}


def _coerce_value(field_name: str, value: str) -> Any:
    if field_name == "bgm_volume":
        return float(value)
    if field_name == "default_shorts_duration_seconds":
        return int(value)
    if field_name == "use_faster_whisper":
        return value.lower() in ("true", "1", "yes")
    return value


def _load_env_values(repo_root: Path) -> dict[str, Any]:
    raw = dict(dotenv_values(repo_root / ".env"))
    for key, value in os.environ.items():
        if key in ENV_TO_FIELD:
            raw[key] = value
    mapped: dict[str, Any] = {}
    for env_key, field_name in ENV_TO_FIELD.items():
        value = raw.get(env_key)
        if value not in (None, ""):
            mapped[field_name] = _coerce_value(field_name, str(value))
    return mapped


def _load_local_values(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "config" / "local.settings.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_settings(repo_root: Path | None = None) -> AppSettings:
    root = repo_root or find_repo_root()
    values: dict[str, Any] = {}
    values.update(_load_env_values(root))
    values.update(_load_local_values(root))
    return AppSettings.model_validate(values)
