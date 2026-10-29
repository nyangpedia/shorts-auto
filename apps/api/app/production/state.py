"""Everything the production screens need about a project, read from its files."""
from __future__ import annotations

import json
from pathlib import Path

from app.production.media import media_duration
from app.production.models import ConceptKit, ProductionState, SceneItem, VideoSceneItem
from app.production.paths import (
    CONCEPT_KIT_FILENAME,
    SCENE_DATA_FILENAME,
    SCENES_DIR_NAME,
    TTS_AUDIO_FILENAME,
    VIDEO_SCENES_FILENAME,
)


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def get_production_state(project_dir: Path, project_id: str | None = None) -> ProductionState:
    pid = project_id or project_dir.name
    asset_url = f"/api/projects/{pid}/production/scenes/"
    audio = project_dir / TTS_AUDIO_FILENAME

    blocks = _read_json(project_dir / SCENE_DATA_FILENAME) or []
    kit_data = _read_json(project_dir / CONCEPT_KIT_FILENAME)
    planned = _read_json(project_dir / VIDEO_SCENES_FILENAME)

    scenes: list[VideoSceneItem] = []
    for raw in planned or []:
        scene = VideoSceneItem.model_validate(raw)
        stem = f"scene_{scene.scene_id:02d}"
        folder = project_dir / SCENES_DIR_NAME
        if (folder / f"{stem}_start.png").exists():
            scene.start_image_url = f"{asset_url}{stem}_start.png"
        if (folder / f"{stem}_final.png").exists():
            scene.final_frame_url = f"{asset_url}{stem}_final.png"
        if (folder / f"{stem}_video.mp4").exists():
            scene.generated_video_url = f"{asset_url}{stem}_video.mp4"
        if scenes and scenes[-1].final_frame_url:
            scene.continuity.prev_final_frame_url = scenes[-1].final_frame_url
        scenes.append(scene)

    final_video = project_dir / "final.mp4"
    rendered = final_video.exists() and final_video.stat().st_size > 1000
    return ProductionState(
        has_audio=audio.exists(),
        audio_filename=TTS_AUDIO_FILENAME if audio.exists() else None,
        duration_seconds=media_duration(audio) if audio.exists() else None,
        has_scene_data=bool(blocks),
        scene_count=len(blocks),
        scenes=[SceneItem.model_validate(b) for b in blocks],
        has_concept_kit=kit_data is not None,
        concept_kit=ConceptKit.model_validate(kit_data) if kit_data else None,
        has_video_scenes=planned is not None,
        video_scene_count=len(scenes),
        video_scenes=scenes,
        has_final_video=rendered,
        final_video_url=f"/api/projects/{pid}/production/final-video" if rendered else None,
        thumbnail_url=f"/api/projects/{pid}/production/thumbnail" if (project_dir / "thumbnail.jpg").exists() else None,
    )
