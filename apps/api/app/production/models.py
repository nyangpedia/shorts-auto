"""Production data: narration blocks, the planned scenes, and request bodies.
Field names are the on-disk format of existing projects (scene_data.json, video_scenes.json, concept_kit.json)."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Lenient(BaseModel):
    """Files written by older versions may carry extra keys; ignore them instead of failing to load."""

    model_config = ConfigDict(extra="ignore")


# ── narration timing (scene_data.json) ──

class SceneTextBlock(_Lenient):
    text: str = ""
    start: float = 0.0
    end: float = 0.0


class SceneItem(_Lenient):
    scene_id: int
    start: float
    end: float
    duration_frames: int
    text_blocks: list[SceneTextBlock] = Field(default_factory=list)


# ── planned scenes (concept_kit.json, video_scenes.json) ──

class ConceptKit(_Lenient):
    visual_style: str = "Cute professional claymation infographic"
    style_id: str = "claymation"
    color_and_lighting: str = ""
    core_objects: list[str] = Field(default_factory=list)  # main character / key objects / setting
    camera_composition: str = "9:16 vertical composition, shallow depth of field"
    continuity_rules: list[str] = Field(default_factory=list)


class ContinuityState(_Lenient):
    camera: str = ""
    subject_state: str = ""
    lighting: str = ""
    handoff_description: str = ""
    prev_final_frame_url: str | None = None  # filled when served, not stored


class VideoSceneItem(_Lenient):
    scene_id: int
    target_duration: float
    start: float
    end: float
    duration_frames: int
    narration: str
    start_image_prompt: str
    video_prompt: str = ""
    continuity: ContinuityState = Field(default_factory=ContinuityState)
    is_locked: bool = False
    last_feedback: str | None = None
    last_image_feedback: str | None = None
    last_video_feedback: str | None = None
    # URLs of the scene's files, filled when served
    start_image_url: str | None = None
    generated_video_url: str | None = None
    final_frame_url: str | None = None


class ProductionState(_Lenient):
    has_audio: bool = False
    audio_filename: str | None = None
    duration_seconds: float | None = None
    has_scene_data: bool = False
    scene_count: int = 0
    scenes: list[SceneItem] = Field(default_factory=list)
    has_concept_kit: bool = False
    concept_kit: ConceptKit | None = None
    has_video_scenes: bool = False
    video_scene_count: int = 0
    video_scenes: list[VideoSceneItem] = Field(default_factory=list)
    has_final_video: bool = False
    final_video_url: str | None = None


# ── request bodies ──

class FeedbackRegenerateRequest(_Lenient):
    feedback: str = ""
    target: str = "image"  # image | video | both | prompt_image | prompt_video
    model: str | None = None
    duration: int = 5
    multi_shots: bool = False
    match_prev_frame: bool = True


class UpdateScenePromptsRequest(_Lenient):
    start_image_prompt: str | None = None
    video_prompt: str | None = None


class RenderShortsRequest(_Lenient):
    title: str | None = None
