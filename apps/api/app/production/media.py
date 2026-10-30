"""ffmpeg/ffprobe helpers: audio tempo, durations, last frames, and the free Ken Burns motion."""
from __future__ import annotations

import subprocess
from pathlib import Path


def run_ffmpeg(*args: str) -> None:
    done = subprocess.run(["ffmpeg", "-y", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if done.returncode != 0:
        raise RuntimeError(f"ffmpeg 실패: {done.stderr[-400:]}")


def media_duration(path: Path) -> float:
    """Seconds, or 0.0 when the file can't be probed."""
    done = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    try:
        return float(done.stdout.strip())
    except ValueError:
        return 0.0


def retime_audio(source: Path, target: Path, tempo: float) -> None:
    """Re-encode to 44.1 kHz WAV, changing speed without changing pitch (tempo 1.0 = just convert)."""
    run_ffmpeg("-i", str(source), "-filter:a", f"atempo={tempo}", "-ar", "44100", str(target))


def grab_last_frame(video: Path, image: Path) -> None:
    run_ffmpeg("-sseof", "-0.1", "-i", str(video), "-update", "1", "-q:v", "1", str(image))


def _kenburns_motion(scene_id: int, frames: int) -> str:
    """zoompan z/x/y expressions; rotates through 5 moves so consecutive scenes never repeat."""
    step = 0.15 / max(frames, 1)
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    progress = f"min(on/{frames},1)"
    moves = [
        f"z='min(zoom+{step:.6f},1.15)':x='{cx}':y='{cy}'",                      # push in
        f"z='if(eq(on,0),1.15,max(zoom-{step:.6f},1.0))':x='{cx}':y='{cy}'",     # pull out
        f"z='1.12':x='(iw-iw/zoom)*{progress}':y='{cy}'",                        # pan left -> right
        f"z='1.12':x='(iw-iw/zoom)*(1-{progress})':y='{cy}'",                    # pan right -> left
        f"z='min(zoom+{step:.6f},1.15)':x='{cx}':y='(ih-ih/zoom)*0.2'",          # push in toward top
    ]
    return moves[(scene_id - 1) % len(moves)]


def _make_kenburns_video(scene_id: int, image_path: Path, video_path: Path, duration: int) -> None:
    frames = duration * 30
    zoom = f"zoompan={_kenburns_motion(scene_id, frames)}:d={frames}:s=1080x1920:fps=30"
    subprocess.run(
        ["ffmpeg", "-y", "-loop", "1", "-i", str(image_path), "-frames:v", str(frames),
         "-vf", f"scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,{zoom}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video_path)],
        capture_output=True,
        check=True,
    )
