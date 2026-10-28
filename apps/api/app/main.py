from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.paths import find_repo_root
from app.core import usage
from app.core.settings import load_settings
from app.jobs.router import create_jobs_router
from app.projects.router import create_projects_router
from app.references.audio import extract_reference_audio
from app.references.openai_clients import OpenAIAnalysisClient, OpenAITranscriptionClient, FasterWhisperClient
from app.references.router import create_references_router
from app.production.router import create_production_router
from app.references.youtube import YouTubeClient
from app.scripts.router import create_scripts_router
from app.topics.router import create_topics_router
from app.daily.router import create_daily_router
from app.uploads.router import create_uploads_router
from app.core.keys_router import create_keys_router


def create_app(
    repo_root: Path | None = None,
    youtube_client_factory=YouTubeClient,
    audio_extractor=extract_reference_audio,
    transcription_client_factory=None,
    analysis_client_factory=OpenAIAnalysisClient,
    upload_transport=None,
) -> FastAPI:
    root = repo_root or find_repo_root()
    settings = load_settings(root)

    if transcription_client_factory is None:
        if settings.use_faster_whisper:
            # Router passes (api_key, model); local whisper ignores both.
            transcription_client_factory = lambda *_: FasterWhisperClient(settings.whisper_model, settings.whisper_device)
        else:
            transcription_client_factory = OpenAITranscriptionClient

    if analysis_client_factory is OpenAIAnalysisClient:
        # Reads settings at call time so keys saved from the settings screen apply without a restart.
        analysis_client_factory = lambda key, model: OpenAIAnalysisClient(key, model, settings.llm_base_url, settings.llm_fallback_list)

    outputs_dir = root / settings.output_dir
    outputs_dir.mkdir(parents=True, exist_ok=True)
    usage.configure(outputs_dir)

    app = FastAPI(title="Shorts Gongbang API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def outputs_dir_provider() -> Path:
        return outputs_dir

    def settings_provider():
        return settings

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/api/usage")
    def usage_today():
        # Free-tier caps observed in 2026-10: ~20 requests/day per Gemini model, ~95 FLUX.2 klein images/day on Workers AI (10k neurons).
        gemini = "generativelanguage" in settings.llm_base_url
        counts = usage.today()
        return {
            "llm": counts["llm"],
            "llm_limit": 20 * (1 + len(settings.llm_fallback_list)) if gemini else None,
            "image": counts["image"],
            "image_limit": 95 if settings.cloudflare_account_id else None,  # FLUX.2 klein 768x1344 ≈ 104 neurons of the free 10k
            "tts": counts["tts"],
        }

    @app.get("/api/settings/status")
    def settings_status():
        return {
            "openai_api_key": bool(settings.openai_api_key),
            "gemini_api_key": bool(settings.gemini_api_key),
            "youtube_api_key": bool(settings.youtube_api_key),
            "higgsfield_api_key": bool(settings.higgsfield_api_key),
            "qwen3_tts_base_url": settings.qwen3_tts_base_url,
            "reference_voice_path": settings.reference_voice_path,
            "reference_voice_text": bool(settings.reference_voice_text),
            "bgm_path": settings.bgm_path,
            "bgm_volume": settings.bgm_volume,
            "output_dir": settings.output_dir,
        }

    app.include_router(create_projects_router(outputs_dir_provider))
    app.include_router(create_jobs_router(outputs_dir_provider))
    app.include_router(
        create_references_router(
            outputs_dir_provider,
            settings_provider,
            youtube_client_factory,
            audio_extractor,
            transcription_client_factory,
            analysis_client_factory,
        )
    )
    app.include_router(create_scripts_router(outputs_dir_provider, settings_provider, analysis_client_factory))
    app.include_router(create_production_router(outputs_dir_provider, settings_provider))
    app.include_router(create_topics_router(outputs_dir_provider))
    app.include_router(create_daily_router(outputs_dir_provider, settings_provider, youtube_client_factory))
    app.include_router(create_uploads_router(root, outputs_dir_provider, upload_transport))
    app.include_router(create_keys_router(root, settings_provider))
    return app


app = create_app()
