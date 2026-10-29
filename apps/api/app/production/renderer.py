"""Final render: fit every scene clip to its narration slot, join them, and hand video + narration +
BGM + timed subtitles + opening title to the Remotion composition (apps/remotion)."""
from __future__ import annotations

import json
import logging
import math
import shutil
import subprocess
from pathlib import Path

from app.core.paths import find_repo_root
from app.core.settings import AppSettings
from app.production.media import _make_kenburns_video, media_duration, run_ffmpeg
from app.production.paths import RAW_STT_FILENAME, SCENE_DATA_FILENAME, TTS_AUDIO_FILENAME, load_scene_list, scene_asset
from app.production.word_timing import assign_word_times, one_line_chunks, transcribe_words

logger = logging.getLogger(__name__)
RENDER_FPS = 24
WORK_DIR = "_render_tmp"
FINAL_VIDEO = "final.mp4"


def _fit_clip(source: Path, seconds: float, target: Path) -> None:
    """Stretch or squeeze the clip to exactly `seconds` (no frozen tail, no cut ending) and fill 9:16."""
    speed = seconds / max(media_duration(source), 0.1)
    run_ffmpeg(
        "-i", str(source),
        "-vf", f"setpts={speed:.6f}*PTS,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps={RENDER_FPS}",
        "-t", f"{seconds:.3f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(target),
    )


def build_scene_track(project_dir: Path, work: Path) -> tuple[Path, list[float]]:
    """One continuous video of all scenes, each lasting as long as its narration. Returns (video, durations)."""
    durations, clips = [], []
    for scene in load_scene_list(project_dir):
        scene_id = int(scene["scene_id"])
        seconds = float(scene.get("target_duration") or 0) or 6.0
        source = scene_asset(project_dir, scene_id, "video")
        if not (source.exists() and source.stat().st_size > 1000):
            picture = scene_asset(project_dir, scene_id, "start")
            if not picture.exists():
                raise FileNotFoundError(f"{scene_id}번 씬에 이미지도 영상도 없습니다.")
            source = work / f"kenburns_{scene_id:02d}.mp4"  # a still gets a slow camera move, never a frozen frame
            _make_kenburns_video(scene_id, picture, source, math.ceil(seconds))
        clip = work / f"norm_scene_{scene_id:02d}.mp4"
        _fit_clip(source, seconds, clip)
        clips.append(clip)
        durations.append(seconds)
    listing = work / "concat_list.txt"
    listing.write_text("\n".join(f"file '{c.resolve()}'" for c in clips), encoding="utf-8")
    joined = work / "concatenated.mp4"
    run_ffmpeg("-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined))
    return joined, durations


def subtitle_blocks(project_dir: Path) -> list[dict]:
    """The script's timed blocks (scene_data), or the raw recognition as a last resort."""
    def load(name: str):
        try:
            return json.loads((project_dir / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    blocks = []
    for scene in load(SCENE_DATA_FILENAME):
        parts = scene.get("text_blocks") or [{**scene, "text": scene.get("subtitle") or scene.get("text") or scene.get("narration") or ""}]
        blocks += [{"start": float(p.get("start", 0)), "end": float(p.get("end", 0)), "text": str(p.get("text", "")).strip()} for p in parts]
    if not any(b["text"] for b in blocks):
        blocks = [{"start": float(s.get("start", 0)), "end": float(s.get("end", 0)), "text": str(s.get("text", "")).strip()} for s in load(RAW_STT_FILENAME)]
    return [b for b in blocks if b["text"]]


def timed_subtitles(project_dir: Path, audio: Path, settings: AppSettings) -> list[dict]:
    """One-line chunks with per-word times from the narration itself (the spoken word gets highlighted).
    If recognition fails, words are spread evenly inside their blocks instead."""
    blocks = subtitle_blocks(project_dir)
    try:
        heard = transcribe_words(audio, settings.whisper_model, settings.whisper_device)
    except Exception as exc:  # recognition is best effort; even spacing still beats no subtitles
        logger.warning("word timing unavailable, spacing words evenly: %s", exc)
        heard = []
    return one_line_chunks(assign_word_times(blocks, heard))


def opening_title(project_dir: Path, title: str | None) -> str | None:
    """The 0–2 s title: the one passed in, else the project title (never the placeholder "untitled")."""
    if title and title.strip():
        return title.strip()
    try:
        saved = json.loads((project_dir / "project.json").read_text(encoding="utf-8")).get("project_title", "").strip()
    except (OSError, ValueError):
        return None
    return saved if saved and saved != "untitled" else None


def _mark_rendered(project_dir: Path) -> None:
    from app.projects.progress import update_progress

    update_progress(
        project_dir.parent, project_dir.name,
        steps={"Render": ("succeeded", "Final 9:16 shorts video rendered with speed sync & subtitles.")},
        files={"final_video": FINAL_VIDEO},
    )


def render_final_shorts(project_dir: Path, settings: AppSettings, title: str | None = None) -> Path:
    narration = project_dir / TTS_AUDIO_FILENAME
    if not narration.exists():
        raise FileNotFoundError("내레이션 음성이 없습니다. 음성을 먼저 만들어주세요.")
    if not load_scene_list(project_dir):
        raise ValueError("렌더링할 씬이 없습니다.")
    work = project_dir / "scenes" / WORK_DIR
    work.mkdir(parents=True, exist_ok=True)

    video, durations = build_scene_track(project_dir, work)
    repo = find_repo_root()
    # Remotion copies publicDir into its bundle, so it is the project folder only (the repo root would drag
    # in pnpm's node_modules symlinks, which Windows refuses to copy without admin rights).
    public = project_dir.resolve()
    rel = lambda p: p.resolve().relative_to(public).as_posix()  # noqa: E731

    bgm_source = repo / settings.bgm_path
    bgm = None
    if bgm_source.exists() and bgm_source.stat().st_size > 1000:
        bgm = work / f"bgm{bgm_source.suffix}"
        shutil.copyfile(bgm_source, bgm)

    props = {
        "videoSrc": rel(video),
        "audioSrc": rel(narration),
        "bgmSrc": rel(bgm) if bgm else None,
        "bgmVolume": float(settings.bgm_volume) if bgm else 0.15,
        "subtitles": timed_subtitles(project_dir, narration, settings),
        "durationInFrames": max(RENDER_FPS, round(media_duration(narration) * RENDER_FPS)),
        "title": opening_title(project_dir, title),
        "sceneStarts": [round(sum(durations[:i]), 3) for i in range(1, len(durations))],
    }
    props_file = work / "remotion_props.json"
    props_file.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")

    output = project_dir / FINAL_VIDEO
    done = subprocess.run(
        ["node", str((repo / "apps" / "remotion" / "render.mjs").resolve()),
         f"--props={props_file.resolve()}", f"--output={output.resolve()}", f"--public={public}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(repo),
    )
    if done.returncode != 0:
        raise RuntimeError(f"Remotion 렌더링 실패: {(done.stderr or done.stdout)[-1500:]}")
    _mark_rendered(project_dir)
    return output
