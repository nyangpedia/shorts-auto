"""Scene clips: a free Ken Burns move over the still, or a paid Higgsfield video model.

With "match previous frame", scene N starts from the last frame of scene N-1 and (on models that take
an end frame) lands on scene N's own picture, so consecutive clips flow as one take.
"""
from __future__ import annotations

from pathlib import Path

from app.core.settings import AppSettings
from app.production.images import HIGGSFIELD_ALIASES, download, higgsfield_run
from app.production.media import _make_kenburns_video, grab_last_frame
from app.production.paths import find_scene, load_scene_list, scene_asset

_TAKES_END_FRAME = ("kling", "seedance", "minimax")


def _clip_options(model: str, start: Path, end: Path | None, seconds: int) -> list[str]:
    opts = ["--start-image", str(start)]
    if end is not None and any(k in model for k in _TAKES_END_FRAME):
        opts += ["--end-image", str(end)]
    if "minimax" in model:
        opts += ["--resolution", "2K"]
    elif "grok" in model:
        opts += ["--resolution", "720p"]
    if "kling" in model:
        # multi-shot needs a prompt list we don't send; Kling clips are 5 or 10 s
        opts += ["--multi-shots", "false", "--duration", "10" if seconds >= 8 else "5"]
    elif any(k in model for k in ("seedance", "minimax", "grok")):
        opts += ["--duration", "5"]  # these models only make 5 s clips
    else:
        opts += ["--duration", str(seconds)]
    return opts


def generate_scene_video_for_project(
    project_dir: Path,
    scene_id: int,
    settings: AppSettings,
    model_name: str = "kenburns",
    duration: int = 5,
    multi_shots: bool = False,  # accepted for API compatibility; single-prompt clips only
    match_prev_frame: bool = True,
) -> Path:
    model = HIGGSFIELD_ALIASES.get(model_name, model_name)
    scene = find_scene(load_scene_list(project_dir), scene_id)
    picture = scene_asset(project_dir, scene_id, "start")
    if not picture.exists():
        raise FileNotFoundError(f"{scene_id}번 씬 이미지가 없습니다. 이미지를 먼저 만들어주세요.")
    clip = scene_asset(project_dir, scene_id, "video")
    last_frame = scene_asset(project_dir, scene_id, "final")

    if model == "kenburns":
        _make_kenburns_video(scene_id, picture, clip, duration)
        start = picture
    else:
        previous_last = scene_asset(project_dir, scene_id - 1, "final") if scene_id > 1 else None
        chained = bool(match_prev_frame and previous_last and previous_last.exists())
        start, end = (previous_last, picture) if chained else (picture, None)
        prompt = scene.get("video_prompt") or f"{scene.get('start_image_prompt', '')}, subtle cinematic motion"
        url = higgsfield_run(model or "kling_o3_flf", prompt, extra=_clip_options(model, start, end, duration), timeout_min=20)
        download(url, clip)

    try:
        grab_last_frame(clip, last_frame)
    except RuntimeError:
        last_frame.write_bytes(start.read_bytes())
    return clip

