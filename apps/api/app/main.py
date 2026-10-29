"""쇼츠공방 API: wires settings, the outputs folder and every step's router into one FastAPI app.
The factories are parameters so tests can swap in fakes for YouTube, yt-dlp, speech and LLM calls."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import usage
from app.core.keys_router import create_keys_router
from app.core.paths import find_repo_root
from app.core.settings import load_settings
from app.daily.router import create_daily_router
from app.jobs.router import create_jobs_router
from app.production.router import create_production_router
from app.projects.router import create_projects_router
from app.references.audio import extract_reference_audio
from app.references.openai_clients import FasterWhisperClient, OpenAIAnalysisClient, OpenAITranscriptionClient
from app.references.router import create_references_router
from app.references.youtube import YouTubeClient
from app.scripts.router import create_scripts_router
from app.topics.router import create_topics_router
from app.uploads.router import create_uploads_router

WEB_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"]  # the Vite dev server
# Free-tier caps observed in 2026-10: ~20 requests/day per Gemini model; Workers AI's 10k daily
# neurons ≈ 95 FLUX.2 klein pictures at 768x1344.
GEMINI_DAILY_PER_MODEL = 20
CLOUDFLARE_DAILY_IMAGES = 95


def create_app(
    repo_root: Path | None = None,
    youtube_client_factory=YouTubeClient,
    audio_extractor=extract_reference_audio,
    transcription_client_factory=None,
    analysis_client_factory=OpenAIAnalysisClient,
    upload_transport=None,
) -> FastAPI:
    root = repo_root or find_repo_root()
    settings = load_settings(root)  # one object, updated in place when keys are saved
    outputs = root / settings.output_dir
    outputs.mkdir(parents=True, exist_ok=True)
    usage.configure(outputs)

    if transcription_client_factory is None:
        def transcription_client_factory(_key, _model):  # local Whisper ignores the OpenAI key/model the router passes
            if settings.use_faster_whisper:
                return FasterWhisperClient(settings.whisper_model, settings.whisper_device)
            return OpenAITranscriptionClient(_key, _model)
    if analysis_client_factory is OpenAIAnalysisClient:
        # Built per call from the live settings, so keys saved on the settings screen apply without a restart.
        def analysis_client_factory(key, model):
            return OpenAIAnalysisClient(key, model, settings.llm_base_url, settings.llm_fallback_list)

    def outputs_dir_provider() -> Path:
        return outputs

    def settings_provider():
        return settings

    app = FastAPI(title="Shorts Gongbang API")
    app.add_middleware(CORSMiddleware, allow_origins=WEB_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/api/usage")
    def usage_today():
        counts = usage.today()
        on_gemini = "generativelanguage" in settings.llm_base_url
        return {
            "llm": counts["llm"],
            "llm_limit": GEMINI_DAILY_PER_MODEL * (1 + len(settings.llm_fallback_list)) if on_gemini else None,
            "image": counts["image"],
            "image_limit": CLOUDFLARE_DAILY_IMAGES if settings.cloudflare_account_id else None,
            "tts": counts["tts"],
        }

    for router in (
        create_projects_router(outputs_dir_provider),
        create_jobs_router(outputs_dir_provider),
        create_references_router(outputs_dir_provider, settings_provider, youtube_client_factory, audio_extractor,
                                 transcription_client_factory, analysis_client_factory),
        create_scripts_router(outputs_dir_provider, settings_provider, analysis_client_factory),
        create_production_router(outputs_dir_provider, settings_provider),
        create_topics_router(outputs_dir_provider),
        create_daily_router(outputs_dir_provider, settings_provider, youtube_client_factory),
        create_uploads_router(root, outputs_dir_provider, upload_transport),
        create_keys_router(root, settings_provider),
    ):
        app.include_router(router)
    return app


app = create_app()
