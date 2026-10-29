"""Reading a reference that has no narration: on-screen captions and what happens, from sampled frames.

Music-only Shorts (most "what if" simulations) give an empty transcript. Instead we download a small copy
of the video, take up to MAX_FRAMES evenly spaced frames, and ask the (free, image-capable) Gemini model to
write down the captions and the action in order. That text stands in for the script in the analysis.
"""
from __future__ import annotations

import base64
import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_FRAMES = 24
FRAME_WIDTH = 480
NO_SPEECH_NOTE = "[내레이션 없는 영상: 음악과 화면 자막만 있음. 아래 내용에 없는 대사를 지어내지 말 것]"

SCREEN_PROMPT = """아래 이미지는 유튜브 쇼츠 한 편을 시간 순서대로 캡처한 것이다 (각 이미지 앞에 초 표시).
이 영상에는 말소리가 없다. 화면만 보고 다음 형식으로 적어라:

[초] 자막: 화면에 보이는 글자를 원문 그대로 (없으면 "없음")
     화면: 무엇이 보이고 무슨 일이 일어나는지 한 줄

- 같은 장면이 이어지면 합쳐서 한 번만 쓴다.
- 보이지 않는 내용은 추측하지 않는다.
- 마지막 줄에 "흐름:"으로 시작해 영상 전체가 어떻게 전개되는지 한 문장으로 요약한다.
- 설명은 한국어로, 자막 원문은 원래 언어 그대로 쓴다."""


def download_small_video(url: str, folder: Path, yt_dlp_binary: str) -> Path:
    """A low-resolution copy (enough to read captions) in `folder`."""
    command = [yt_dlp_binary, "-f", "b[height<=480]/bv*[height<=480]/b", "--no-playlist",
               "--output", str(folder / "video.%(ext)s"), url]
    done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    found = sorted(folder.glob("video.*"))
    if done.returncode != 0 or not found:
        raise RuntimeError(f"영상 다운로드 실패: {(done.stderr or done.stdout).strip()[-300:]}")
    return found[0]


def sample_frames(video: Path, folder: Path, seconds: float) -> list[tuple[float, Path]]:
    """Up to MAX_FRAMES frames spread over the video, as (time, jpg)."""
    step = max(1.0, seconds / MAX_FRAMES)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vf", f"fps=1/{step},scale={FRAME_WIDTH}:-2",
                    "-q:v", "4", str(folder / "f_%03d.jpg")], check=True, capture_output=True)
    frames = sorted(folder.glob("f_*.jpg"))[:MAX_FRAMES]
    return [(round(i * step + step / 2, 1), path) for i, path in enumerate(frames)]


def read_screen(frames: list[tuple[float, Path]], client) -> str:
    """Captions + action per moment, written by the image-capable model."""
    content: list[dict] = [{"type": "text", "text": SCREEN_PROMPT}]
    for at, path in frames:
        data = base64.b64encode(path.read_bytes()).decode()
        content += [{"type": "text", "text": f"[{at:.0f}초]"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data}"}}]
    return client.describe(content).strip()


def silent_video_script(reference, client, yt_dlp_binary: str, seconds: float) -> str:
    """Stand-in script for a video without speech: what's on screen if we can read it, else just the title."""
    if reference is None:
        raise ValueError("말소리를 찾지 못했습니다. 내레이션이 있는 영상을 고르세요.")
    gloss = f" ({reference.title_ko})" if reference.title_ko else ""
    head = f"{NO_SPEECH_NOTE}\n제목: {reference.title}{gloss}"
    if not hasattr(client, "describe"):  # no image-capable model configured
        return f"{head}\n(화면을 읽지 못해 제목과 소재로만 분석할 것)"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            reading = read_screen(sample_frames(download_small_video(reference.url, folder, yt_dlp_binary), folder, seconds), client)
        if reading:
            return f"{head}\n\n[화면 내용]\n{reading}"
    except Exception as exc:  # the title alone still beats an empty script
        logger.warning("could not read the screen of %s: %s", reference.video_id, exc)
    return f"{head}\n(화면을 읽지 못해 제목과 소재로만 분석할 것)"
