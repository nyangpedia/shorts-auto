"""Production pipeline entry points, gathered for the router: voice → scenes → images → clips → state."""
from app.production.images import draw_image, generate_scene_image_for_project
from app.production.media import media_duration as _get_audio_duration
from app.production.motion import generate_scene_video_for_project
from app.production.paths import (
    CONCEPT_KIT_FILENAME,
    RAW_STT_FILENAME,
    SCENE_DATA_FILENAME,
    SCENES_DIR_NAME,
    TTS_AUDIO_FILENAME,
    VIDEO_SCENES_FILENAME,
)
from app.production.revise import refine_and_regenerate_scene, update_scene_prompts_for_project
from app.production.scenes import generate_concept_kit_and_video_scenes, script_beats
from app.production.state import get_production_state
from app.production.voice import align_subtitles_and_scenes_for_project, generate_tts_for_project


def calibrate_scenes_with_stt(scenes, stt_segments, total_audio_duration):
    """Scenes are timed from word-level narration timings when they are planned; nothing to redo here."""
    return scenes


__all__ = [
    "CONCEPT_KIT_FILENAME", "RAW_STT_FILENAME", "SCENE_DATA_FILENAME", "SCENES_DIR_NAME", "TTS_AUDIO_FILENAME",
    "VIDEO_SCENES_FILENAME", "align_subtitles_and_scenes_for_project", "calibrate_scenes_with_stt", "draw_image",
    "generate_concept_kit_and_video_scenes", "generate_scene_image_for_project", "generate_scene_video_for_project",
    "generate_tts_for_project", "get_production_state",
    "refine_and_regenerate_scene", "script_beats", "update_scene_prompts_for_project", "_get_audio_duration",
]
