"""Reference step API: find a Short, pick it, get its audio, transcribe it, analyse why it worked."""
from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path
from typing import Callable

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.core.settings import AppSettings
from app.projects.models import WORKFLOW_STEPS
from app.projects.progress import REFERENCE_FILE_KEYS, SCRIPT_FILE_KEYS, job, update_progress
from app.projects.service import read_project, save_project
from app.references.analysis import build_analysis_prompt, write_reference_analysis
from app.references.audio import AudioExtractionError, extract_reference_audio, save_uploaded_audio, validate_audio_upload_name
from app.references.files import (
    CANDIDATES_FILE,
    REFERENCE_ANALYSIS_FILE,
    REFERENCE_ANALYSIS_MARKDOWN_FILE,
    REFERENCE_RAW_STT_FILE,
    REFERENCE_SCRIPT_FILE,
    SELECTED_REFERENCE_FILE,
    clear_derived_reference_outputs,
    clear_downstream_reference_outputs,
    clear_reference_analysis_outputs,
    clear_reference_audio_files,
    read_reference_candidates,
    read_reference_state,
    read_selected_reference,
    write_reference_candidates,
    write_selected_reference,
)
from app.references.models import DirectReferenceRequest, ReferenceCandidate, ReferenceSearchRequest, SelectReferenceRequest
from app.references.openai_clients import (
    AnalysisClient,
    OpenAIAnalysisClient,
    OpenAITranscriptionClient,
    TranscriptionClient,
    write_reference_stt_outputs,
)
from app.references.youtube import YouTubeClient, sort_by_vs_ratio

logger = logging.getLogger(__name__)
SCRIPT_GENERATED_FILE_KEYS = SCRIPT_FILE_KEYS  # older name, imported elsewhere
SEARCH_CACHE_FILE = "_search_cache.json"
_HANGUL = re.compile(r"[가-힣]")
AFTER_STT = WORKFLOW_STEPS[2:]  # Analysis … Render
AFTER_ANALYSIS = ("Candidates", "Script", "Production", "Render")


def add_korean_titles(candidates: list[ReferenceCandidate], make_client: Callable[[], AnalysisClient]) -> list[ReferenceCandidate]:
    """One LLM call glosses every non-Korean title; search still succeeds if it fails."""
    foreign = [c for c in candidates if not _HANGUL.search(c.title)]
    if not foreign:
        return candidates
    lines = "\n".join(f"{i}. {c.title}" for i, c in enumerate(foreign))
    prompt = (
        "다음 유튜브 쇼츠 제목들이 무슨 내용인지 한국어로 짧게(30자 이내) 옮겨라. "
        "해시태그는 빼고 내용만. 같은 순서로 JSON {\"titles\": [\"...\"]} 만 출력.\n\n" + lines
    )
    try:
        titles = make_client().analyze(prompt)["titles"]
    except Exception as exc:  # translation is a nicety; never fail the search over it
        logger.warning("title translation skipped: %s", exc)
        return candidates
    if len(titles) != len(foreign):
        return candidates
    glossed = {c.video_id: str(t).strip() for c, t in zip(foreign, titles)}
    return [c.model_copy(update={"title_ko": glossed.get(c.video_id)}) for c in candidates]


def _error_text(exc: Exception) -> str:
    return str(exc) or type(exc).__name__


def create_references_router(
    outputs_dir_provider: Callable[[], Path],
    settings_provider: Callable[[], AppSettings],
    youtube_client_factory: Callable[[str], YouTubeClient] = YouTubeClient,
    audio_extractor: Callable[[Path, str, str], Path] = extract_reference_audio,
    transcription_client_factory: Callable[[str, str], TranscriptionClient] = OpenAITranscriptionClient,
    analysis_client_factory: Callable[[str, str], AnalysisClient] = OpenAIAnalysisClient,
) -> APIRouter:
    router = APIRouter(prefix="/api/projects/{project_id}/reference", tags=["reference"])

    # ── search, cached per day on disk (a genre button is 6 searches = 600 quota units) ──
    def cached_search(payload: ReferenceSearchRequest, outputs: Path, settings: AppSettings) -> list[ReferenceCandidate]:
        key = f"{date.today()}|{payload.model_dump_json()}"
        cache_path = outputs / SEARCH_CACHE_FILE
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cache = {}
        if key in cache:
            return [ReferenceCandidate.model_validate(item) for item in cache[key]]
        found = add_korean_titles(
            youtube_client_factory(settings.youtube_api_key).search(payload),
            lambda: analysis_client_factory(settings.llm_api_key, settings.openai_analysis_model),
        )
        today = key.split("|", 1)[0]
        cache = {k: v for k, v in cache.items() if k.startswith(today)}  # only today's searches are kept
        cache[key] = [c.model_dump() for c in found]
        cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        return found

    def folder(outputs: Path, project_id: str) -> Path:
        read_project(outputs, project_id)  # 404s / rejects bad ids before touching the disk
        return outputs / project_id

    def audio_replaced(outputs: Path, project_id: str, audio_name: str) -> None:
        """New reference audio: drop everything derived from the old one and wait for transcription."""
        path = outputs / project_id
        clear_reference_audio_files(path, audio_name)
        clear_derived_reference_outputs(path)
        update_progress(
            outputs, project_id, current="STT",
            steps={"STT": ("waiting", "Reference audio is ready for STT.")}, reset=AFTER_STT,
            files={"reference_audio": audio_name}, drop_files=[*REFERENCE_FILE_KEYS, *SCRIPT_FILE_KEYS],
        )

    def fetch_audio(outputs: Path, project_id: str, selected: ReferenceCandidate, settings: AppSettings) -> Path:
        with job(outputs, project_id, "reference_audio_extract", "Extract reference audio", "Extracting reference audio",
                 provider="yt-dlp", command=settings.yt_dlp_binary, inputs=[selected.url], fail_on=(AudioExtractionError,)) as run:
            audio = audio_extractor(outputs / project_id, selected.url, settings.yt_dlp_binary)
            audio_replaced(outputs, project_id, audio.name)
            run.succeed("Reference audio extracted", [audio.name])
        return audio

    @router.get("")
    def get_reference(project_id: str, outputs: Path = Depends(outputs_dir_provider)):
        try:
            return read_reference_state(folder(outputs, project_id)).model_dump()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/search")
    def search_reference(project_id: str, payload: ReferenceSearchRequest,
                         outputs: Path = Depends(outputs_dir_provider), settings: AppSettings = Depends(settings_provider)):
        try:
            with job(outputs, project_id, "youtube_search", "YouTube search", "Searching YouTube",
                     provider="youtube", command="search.list", fail_on=(ValueError, httpx.HTTPError)) as run:
                found = cached_search(payload, outputs, settings)
                write_reference_candidates(folder(outputs, project_id), found)
                run.succeed(f"Found {len(found)} reference candidates", [CANDIDATES_FILE])
            return {"candidates": [c.model_dump() for c in found]}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except (ValueError, httpx.HTTPError) as exc:
            raise HTTPException(status_code=400, detail=_error_text(exc)) from exc

    @router.post("/direct")
    def add_direct_reference(project_id: str, payload: DirectReferenceRequest,
                             outputs: Path = Depends(outputs_dir_provider), settings: AppSettings = Depends(settings_provider)):
        try:
            with job(outputs, project_id, "youtube_direct", "Direct reference metadata", "Fetching direct link metadata",
                     provider="youtube", command="videos.list", fail_on=(ValueError, httpx.HTTPError)) as run:
                video = youtube_client_factory(settings.youtube_api_key).get_direct(payload.url)
                path = folder(outputs, project_id)
                listed = [c for c in read_reference_candidates(path) if c.video_id != video.video_id] + [video]
                listed = sort_by_vs_ratio(listed)
                write_reference_candidates(path, listed)
                run.succeed("Direct reference added", [CANDIDATES_FILE])
            return {"candidate": video.model_dump(), "candidates": [c.model_dump() for c in listed]}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except (ValueError, httpx.HTTPError) as exc:
            raise HTTPException(status_code=400, detail=_error_text(exc)) from exc

    @router.post("/select")
    def select_reference(project_id: str, payload: SelectReferenceRequest, outputs: Path = Depends(outputs_dir_provider)):
        try:
            path = folder(outputs, project_id)
            chosen = next((c for c in read_reference_candidates(path) if c.video_id == payload.video_id), None)
            if chosen is None:
                raise HTTPException(status_code=404, detail="Reference candidate not found")
            clear_downstream_reference_outputs(path)
            write_selected_reference(path, chosen)
            project = read_project(outputs, project_id)
            project.selected_reference_path = SELECTED_REFERENCE_FILE
            project.selected_candidate_id = chosen.video_id
            save_project(outputs, project)
            update_progress(
                outputs, project_id, current="STT",
                steps={"Reference": ("succeeded", "Reference selected."),
                       "STT": ("waiting", "Reference selected. Ready for audio and STT.")},
                reset=AFTER_STT,
                files={"selected_reference": SELECTED_REFERENCE_FILE},
                drop_files=["reference_audio", *REFERENCE_FILE_KEYS, *SCRIPT_FILE_KEYS],
            )
            return {"selected_reference": chosen.model_dump()}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/audio/extract")
    def extract_audio(project_id: str, outputs: Path = Depends(outputs_dir_provider), settings: AppSettings = Depends(settings_provider)):
        try:
            selected = read_selected_reference(folder(outputs, project_id))
            if selected is None:
                raise HTTPException(status_code=400, detail="Select a reference before extracting audio")
            return {"audio_path": fetch_audio(outputs, project_id, selected, settings).name}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except (AudioExtractionError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/audio/upload")
    async def upload_audio(project_id: str, file: UploadFile, outputs: Path = Depends(outputs_dir_provider)):
        try:
            path = folder(outputs, project_id)
            name = validate_audio_upload_name(file.filename or "")
            await save_uploaded_audio(file, path / name)
            audio_replaced(outputs, project_id, name)
            return {"audio_path": name}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/stt")
    def run_reference_stt(project_id: str, outputs: Path = Depends(outputs_dir_provider), settings: AppSettings = Depends(settings_provider)):
        try:
            path = folder(outputs, project_id)
            audio_name = read_project(outputs, project_id).generated_files.get("reference_audio") or "reference_audio.wav"
            audio = path / audio_name
            if not audio.exists():
                selected = read_selected_reference(path)
                if selected is None:
                    raise HTTPException(status_code=400, detail="Reference audio is missing")
                audio = fetch_audio(outputs, project_id, selected, settings)

            with job(outputs, project_id, "reference_stt", "Reference STT", "Running OpenAI STT",
                     provider="openai", command=settings.openai_transcription_model, inputs=[audio.name]) as run:
                update_progress(outputs, project_id, current="STT", steps={"STT": ("running", "Running OpenAI STT.")})
                raw = transcription_client_factory(settings.openai_api_key, settings.openai_transcription_model).transcribe(audio)
                script = write_reference_stt_outputs(path, raw)
                clear_reference_analysis_outputs(path)
                update_progress(
                    outputs, project_id, current="Analysis",
                    steps={"STT": ("succeeded", "Reference STT complete."),
                           "Analysis": ("waiting", "Reference script is ready for analysis.")},
                    reset=AFTER_ANALYSIS,
                    files={"reference_raw_stt": REFERENCE_RAW_STT_FILE, "reference_script": REFERENCE_SCRIPT_FILE},
                    drop_files=["reference_analysis", "reference_analysis_markdown", *SCRIPT_FILE_KEYS],
                )
                run.succeed("Reference STT complete", [REFERENCE_RAW_STT_FILE, REFERENCE_SCRIPT_FILE])
            return {"reference_script": script}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=_error_text(exc)) from exc

    @router.post("/analyze")
    def analyze_reference(project_id: str, outputs: Path = Depends(outputs_dir_provider), settings: AppSettings = Depends(settings_provider)):
        started = False
        try:
            path = folder(outputs, project_id)
            script_path = path / REFERENCE_SCRIPT_FILE
            if not script_path.exists():
                raise HTTPException(status_code=400, detail="Reference script is missing")
            with job(outputs, project_id, "reference_analysis", "Analyze reference script", "Analyzing reference script",
                     provider="openai", command=settings.openai_analysis_model, inputs=[REFERENCE_SCRIPT_FILE]) as run:
                started = True
                clear_reference_analysis_outputs(path)
                update_progress(
                    outputs, project_id, current="Analysis",
                    steps={"Analysis": ("running", "Analyzing reference script.")}, reset=AFTER_ANALYSIS,
                    drop_files=["reference_analysis", "reference_analysis_markdown", *SCRIPT_FILE_KEYS],
                )
                client = analysis_client_factory(settings.llm_api_key, settings.openai_analysis_model)
                analysis = client.analyze(build_analysis_prompt(script_path.read_text(encoding="utf-8")))
                report = write_reference_analysis(path, analysis)
                update_progress(
                    outputs, project_id, current="Candidates",
                    steps={"Analysis": ("succeeded", "Reference analysis complete."),
                           "Candidates": ("waiting", "Ready to generate candidates.")},
                    files={"reference_analysis": REFERENCE_ANALYSIS_FILE, "reference_analysis_markdown": REFERENCE_ANALYSIS_MARKDOWN_FILE},
                )
                run.succeed("Reference analysis complete", [REFERENCE_ANALYSIS_FILE, REFERENCE_ANALYSIS_MARKDOWN_FILE])
            return {"analysis": analysis, "analysis_markdown": report}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except HTTPException:
            raise
        except Exception as exc:
            message = _error_text(exc)
            if started:
                update_progress(outputs, project_id, current="Analysis",
                                steps={"Analysis": ("failed", message), "Candidates": ("waiting", "")})
            raise HTTPException(status_code=400, detail=message) from exc

    # Browsing without a project: a project is only created once the user picks a video,
    # so looking around no longer leaves empty "untitled" projects behind.
    root = APIRouter()

    @root.post("/api/references/search", tags=["reference"])
    def search_without_project(payload: ReferenceSearchRequest, outputs: Path = Depends(outputs_dir_provider),
                               settings: AppSettings = Depends(settings_provider)):
        try:
            found = cached_search(payload, outputs, settings)
        except (ValueError, httpx.HTTPError) as exc:
            raise HTTPException(status_code=400, detail=_error_text(exc)) from exc
        return {"candidates": [c.model_dump() for c in found]}

    root.include_router(router)
    return root
