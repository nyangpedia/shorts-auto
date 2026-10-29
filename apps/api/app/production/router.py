"""Production API: narration, scene planning, per-scene pictures and clips, and the final render."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.core.settings import AppSettings
from app.production.models import FeedbackRegenerateRequest, ProductionState, RenderShortsRequest, ThumbnailRequest, UpdateScenePromptsRequest
from app.production.renderer import FINAL_VIDEO, render_final_shorts
from app.production.thumbnail import THUMBNAIL, make_thumbnail
from app.production.service import (
    CONCEPT_KIT_FILENAME,
    RAW_STT_FILENAME,
    SCENE_DATA_FILENAME,
    SCENES_DIR_NAME,
    TTS_AUDIO_FILENAME,
    VIDEO_SCENES_FILENAME,
    align_subtitles_and_scenes_for_project,
    generate_concept_kit_and_video_scenes,
    generate_scene_image_for_project,
    generate_scene_video_for_project,
    generate_tts_for_project,
    get_production_state,
    refine_and_regenerate_scene,
    update_scene_prompts_for_project,
)
from app.projects.progress import job, update_progress
from app.projects.service import read_project

# Only the files the scene steps write can be fetched (no "../" tricks).
_SCENE_FILE = re.compile(r"^scene_\d{2}_(start|final|end)\.png$|^scene_\d{2}_video\.mp4$")
_NARRATION_DONE = {
    "Production": ("succeeded", "TTS and scene alignment complete."),
    "Render": ("waiting", "Ready for visual concept & final rendering."),
}


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc) or type(exc).__name__)


def create_production_router(outputs_dir_provider: Callable[[], Path], settings_provider: Callable[[], AppSettings]) -> APIRouter:
    router = APIRouter(prefix="/api/projects/{project_id}/production", tags=["production"])
    Outputs = Depends(outputs_dir_provider)
    Settings = Depends(settings_provider)

    def folder(outputs: Path, project_id: str) -> Path:
        try:
            read_project(outputs, project_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        return outputs / project_id

    def state(path: Path, project_id: str) -> dict:
        return get_production_state(path, project_id).model_dump()

    def scene_work(project_id: str, outputs: Path, work: Callable[[Path], object]) -> dict:
        """Per-scene actions: run, then return the refreshed production state; any failure → 400."""
        path = folder(outputs, project_id)
        try:
            work(path)
        except Exception as exc:
            raise _bad_request(exc) from exc
        return state(path, project_id)

    @router.get("", response_model=ProductionState)
    def get_state(project_id: str, outputs: Path = Outputs):
        return get_production_state(folder(outputs, project_id), project_id)

    @router.get("/audio")
    def get_audio(project_id: str, outputs: Path = Outputs):
        audio = folder(outputs, project_id) / TTS_AUDIO_FILENAME
        if not audio.exists():
            raise HTTPException(status_code=404, detail="TTS audio not found")
        return FileResponse(path=str(audio), media_type="audio/wav", filename=TTS_AUDIO_FILENAME)

    @router.post("/tts")
    def generate_tts(project_id: str, outputs: Path = Outputs, settings: AppSettings = Settings):
        path = folder(outputs, project_id)
        try:
            with job(outputs, project_id, "production_tts", "Generate 1.2x TTS audio", f"Generating TTS voice with {settings.tts_provider}",
                     provider=settings.tts_provider, command=settings.tts_provider, inputs=["final_script.md"]) as run:
                generate_tts_for_project(path, settings)
                run.note("Transcribing and aligning scenes")
                align_subtitles_and_scenes_for_project(path, settings)
                update_progress(outputs, project_id, steps=_NARRATION_DONE, files={
                    "tts_audio": TTS_AUDIO_FILENAME, "raw_stt": RAW_STT_FILENAME, "scene_data": SCENE_DATA_FILENAME})
                run.succeed("1.2x TTS audio and scene data generated successfully", [TTS_AUDIO_FILENAME, RAW_STT_FILENAME, SCENE_DATA_FILENAME])
        except Exception as exc:
            raise _bad_request(exc) from exc
        return state(path, project_id)

    @router.get("/scenes/{filename}")
    def get_scene_file(project_id: str, filename: str, outputs: Path = Outputs):
        target = folder(outputs, project_id) / SCENES_DIR_NAME / filename
        if not _SCENE_FILE.fullmatch(filename) or not target.exists():
            raise HTTPException(status_code=404, detail="Scene asset not found")
        kind = "video/mp4" if filename.endswith(".mp4") else "image/png"
        # Pictures get redrawn under the same name, so never let the browser reuse an old copy.
        return FileResponse(path=str(target), media_type=kind, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

    @router.post("/concepts")
    def generate_concepts(project_id: str, style: str | None = None, outputs: Path = Outputs, settings: AppSettings = Settings):
        path = folder(outputs, project_id)
        try:
            with job(outputs, project_id, "production_concepts", "Generate visual concept kit and continuous video scenes",
                     "Designing concept kit and continuity video scenes", provider="llm", command="generate_concepts",
                     inputs=["final_script.md", SCENE_DATA_FILENAME]) as run:
                generate_concept_kit_and_video_scenes(path, settings, style)
                # New scenes make the old pictures/clips stale (other style, other scene count). Left in place they
                # counted as "done" and mixed styles in the final video, so they go once the new scenes exist.
                for pattern in ("scene_*_start.png", "scene_*_end.png", "scene_*_final.png", "scene_*_video.mp4"):
                    for stale in (path / SCENES_DIR_NAME).glob(pattern):
                        stale.unlink(missing_ok=True)
                update_progress(outputs, project_id, files={"concept_kit": CONCEPT_KIT_FILENAME, "video_scenes": VIDEO_SCENES_FILENAME})
                run.succeed("Concept kit and continuous video scenes created", [CONCEPT_KIT_FILENAME, VIDEO_SCENES_FILENAME])
        except Exception as exc:
            raise _bad_request(exc) from exc
        return state(path, project_id)

    @router.post("/scenes/{scene_id}/image")
    def generate_scene_image(project_id: str, scene_id: int, model: str = "cloudflare", outputs: Path = Outputs, settings: AppSettings = Settings):
        return scene_work(project_id, outputs, lambda path: generate_scene_image_for_project(path, scene_id, settings, model_name=model))

    @router.post("/scenes/images")
    def generate_all_scene_images(project_id: str, model: str = "cloudflare", outputs: Path = Outputs, settings: AppSettings = Settings):
        def draw_all(path: Path) -> None:
            for scene in get_production_state(path, project_id).video_scenes:
                if not scene.is_locked:
                    generate_scene_image_for_project(path, scene.scene_id, settings, model_name=model)
        return scene_work(project_id, outputs, draw_all)

    @router.post("/scenes/{scene_id}/video")
    def generate_scene_video(project_id: str, scene_id: int, model: str = "parallax", duration: int = 5, multi_shots: bool = False,
                             match_prev_frame: bool = True, outputs: Path = Outputs, settings: AppSettings = Settings):
        return scene_work(project_id, outputs, lambda path: generate_scene_video_for_project(
            path, scene_id, settings, model_name=model, duration=duration, multi_shots=multi_shots, match_prev_frame=match_prev_frame))

    @router.post("/scenes/{scene_id}/feedback-regenerate")
    def feedback_regenerate_scene(project_id: str, scene_id: int, req: FeedbackRegenerateRequest, outputs: Path = Outputs, settings: AppSettings = Settings):
        return scene_work(project_id, outputs, lambda path: refine_and_regenerate_scene(
            path, scene_id, feedback=req.feedback, target=req.target, settings=settings, model_name=req.model,
            duration=req.duration, multi_shots=req.multi_shots, match_prev_frame=req.match_prev_frame))

    @router.put("/scenes/{scene_id}/prompts")
    def update_scene_prompts(project_id: str, scene_id: int, req: UpdateScenePromptsRequest, outputs: Path = Outputs):
        return scene_work(project_id, outputs, lambda path: update_scene_prompts_for_project(
            path, scene_id, start_image_prompt=req.start_image_prompt, video_prompt=req.video_prompt))

    @router.post("/render")
    def render_shorts(project_id: str, req: RenderShortsRequest | None = None, outputs: Path = Outputs, settings: AppSettings = Settings):
        path = folder(outputs, project_id)
        try:
            with job(outputs, project_id, "production_render", "Render final shorts video with speed sync and subtitles",
                     "Rendering 9:16 shorts video with subtitles and BGM", provider="hyperframes", command="render_final_shorts",
                     inputs=[VIDEO_SCENES_FILENAME, TTS_AUDIO_FILENAME, SCENE_DATA_FILENAME]) as run:
                render_final_shorts(path, settings, title=req.title if req else None)  # falls back to the project title
                run.succeed("Final shorts video rendered successfully", [FINAL_VIDEO])
        except Exception as exc:
            raise _bad_request(exc) from exc
        return state(path, project_id)

    @router.get("/final-video")
    def get_final_video(project_id: str, outputs: Path = Outputs):
        video = folder(outputs, project_id) / FINAL_VIDEO
        if not video.exists():
            raise HTTPException(status_code=404, detail="final.mp4 영상이 아직 생성되지 않았습니다.")
        return FileResponse(path=str(video), media_type="video/mp4", filename=f"{project_id}_final.mp4")

    @router.post("/thumbnail")
    def create_thumbnail(project_id: str, req: ThumbnailRequest, outputs: Path = Outputs):
        path = folder(outputs, project_id)
        try:
            make_thumbnail(path, req.scene_id, req.title)
        except (FileNotFoundError, ValueError) as exc:
            raise _bad_request(exc) from exc
        update_progress(outputs, project_id, files={"thumbnail": THUMBNAIL})
        return {"thumbnail_url": f"/api/projects/{project_id}/production/thumbnail"}

    @router.get("/thumbnail")
    def get_thumbnail(project_id: str, outputs: Path = Outputs):
        image = folder(outputs, project_id) / THUMBNAIL
        if not image.exists():
            raise HTTPException(status_code=404, detail="썸네일이 아직 없습니다.")
        return FileResponse(path=str(image), media_type="image/jpeg", filename=f"{project_id}_thumbnail.jpg")

    return router
