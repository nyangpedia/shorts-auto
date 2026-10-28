"""설정 화면: each install enters its own API keys; they are written to the repo's .env.

Key values never leave the server: the API only reports whether each key is set.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from dotenv import set_key, unset_key
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.settings import AppSettings, load_settings

# env name -> settings field. Only these can be written from the UI.
EDITABLE_KEYS = {
    "GEMINI_API_KEY": "gemini_api_key",
    "YOUTUBE_API_KEY": "youtube_api_key",
    "CLOUDFLARE_ACCOUNT_ID": "cloudflare_account_id",
    "CLOUDFLARE_API_TOKEN": "cloudflare_api_token",
    "OPENAI_API_KEY": "openai_api_key",
}
# A Gemini key alone should be enough to run: point the LLM at Gemini unless the user configured otherwise.
GEMINI_LLM_DEFAULTS = {
    "LLM_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "OPENAI_ANALYSIS_MODEL": "gemini-3.5-flash",
    "LLM_FALLBACK_MODELS": "gemini-3.6-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-flash-lite-latest",
}


class KeysUpdate(BaseModel):
    # "" clears a key; omitted keys are left alone.
    values: dict[str, str] = Field(max_length=len(EDITABLE_KEYS))


def create_keys_router(repo_root: Path, settings_provider: Callable[[], AppSettings]) -> APIRouter:
    router = APIRouter(prefix="/api/settings/keys", tags=["settings"])
    env_path = repo_root / ".env"

    def status() -> dict:
        settings = settings_provider()
        return {"keys": {env: bool(getattr(settings, field)) for env, field in EDITABLE_KEYS.items()}}

    @router.get("")
    def get_keys():
        return status()

    @router.put("")
    def put_keys(payload: KeysUpdate):
        for env, value in payload.values.items():
            if env not in EDITABLE_KEYS:
                raise HTTPException(status_code=400, detail=f"설정할 수 없는 항목입니다: {env}")
            if "\n" in value or "\r" in value or len(value) > 300:
                raise HTTPException(status_code=400, detail=f"{env} 값 형식이 올바르지 않습니다.")
        env_path.touch(exist_ok=True)
        for env, value in payload.values.items():
            if value.strip():
                set_key(str(env_path), env, value.strip(), quote_mode="never")
            else:
                unset_key(str(env_path), env, quote_mode="never")

        settings = settings_provider()
        fresh = load_settings(repo_root)
        if fresh.gemini_api_key and not fresh.openai_api_key and not fresh.llm_base_url:
            for env, value in GEMINI_LLM_DEFAULTS.items():
                set_key(str(env_path), env, value, quote_mode="never")
            fresh = load_settings(repo_root)
        # Routers hold this same settings object, so updating it in place applies the keys without a restart.
        for field in AppSettings.model_fields:
            setattr(settings, field, getattr(fresh, field))
        return status()

    return router
