"""Getting the reference's sound: download it with yt-dlp, or accept a file the user uploads."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".webm"}
MAX_AUDIO_UPLOAD_BYTES = 200 * 1024 * 1024
UPLOAD_CHUNK_SIZE = 1024 * 1024


class AudioExtractionError(RuntimeError):
    pass


def validate_audio_upload_name(filename: str) -> str:
    """The stored name for an upload ("reference_audio.mp3"), or ValueError for an unsupported type."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise ValueError("Audio upload must be wav, mp3, m4a, aac, or webm")
    return f"reference_audio{ext}"


def default_runner(command: list[str]) -> tuple[int, str, str]:
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    return done.returncode, done.stdout, done.stderr


async def save_uploaded_audio(file: Any, output_path: Path, max_bytes: int = MAX_AUDIO_UPLOAD_BYTES) -> Path:
    """Stream an upload to disk in chunks, refusing empty or oversized files without leaving partial ones."""
    fd, temp_name = tempfile.mkstemp(dir=output_path.parent, prefix=f".{output_path.name}.", suffix=".tmp")
    written = 0
    try:
        with os.fdopen(fd, "wb") as handle:
            while chunk := await file.read(UPLOAD_CHUNK_SIZE):
                written += len(chunk)
                if written > max_bytes:
                    raise ValueError("Audio upload is too large")
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        if written == 0:
            raise ValueError("Audio upload must not be empty")
        os.replace(temp_name, output_path)
        return output_path
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def extract_reference_audio(
    project_dir: Path,
    url: str,
    yt_dlp_binary: str,
    runner: Callable[[list[str]], tuple[int, str, str]] = default_runner,
) -> Path:
    """Download the video's audio track as reference_audio.wav."""
    target = project_dir / "reference_audio.wav"
    command = [yt_dlp_binary, "--extract-audio", "--audio-format", "wav",
               "--output", str(project_dir / "reference_audio.%(ext)s"), url]
    try:
        code, out, err = runner(command)
    except FileNotFoundError as exc:
        raise AudioExtractionError(f"yt-dlp binary not found: {yt_dlp_binary}") from exc
    if code != 0:
        raise AudioExtractionError(err.strip() or out.strip() or "yt-dlp failed")
    if not target.exists():
        raise AudioExtractionError("yt-dlp completed but reference_audio.wav was not created")
    return target
