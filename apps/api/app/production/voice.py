"""Narration: text-to-speech, then timing the script against the spoken audio.

Subtitle text comes straight from the confirmed script; speech recognition only supplies *when* each
part is said. (Recognised Korean is full of near-miss spellings, so it is never shown to viewers.)
"""
from __future__ import annotations

import asyncio
import base64
import re
from pathlib import Path

from app.core import usage
from app.core.settings import AppSettings
from app.production.media import retime_audio
from app.production.models import SceneItem, SceneTextBlock
from app.production.numbers import digits_for_subtitles
from app.production.paths import (
    FPS,
    NARRATION_SPEED,
    RAW_STT_FILENAME,
    SCENE_DATA_FILENAME,
    TTS_AUDIO_FILENAME,
    read_final_script,
    write_json,
)

SCENE_GROUP_SECONDS = 6.0  # scene_data groups subtitle blocks into ~6 s chunks (informational only)


# ── text to speech ──────────────────────────────────────────────────────────

def _synthesize_gemini(script: str, settings: AppSettings, raw_path: Path) -> None:
    from google import genai

    if not settings.gemini_api_key:
        raise RuntimeError("Gemini API 키가 없습니다. 설정 화면에서 넣어주세요.")
    # Keep the client in a variable for the whole call: a throwaway Client() can be garbage-collected
    # mid-request, which closes its connection ("Cannot send a request, as the client has been closed").
    client = genai.Client(api_key=settings.gemini_api_key)
    reply = client.interactions.create(
        model=settings.gemini_tts_model,
        input=[{
            "type": "user_input",
            "content": [{"type": "text", "text": script, "annotations": [{"type": "speech_metadata", "style": settings.gemini_tts_style}]}],
        }],
        response_format={"type": "audio"},
        generation_config={"speech_config": [{"voice": settings.gemini_tts_voice}]},
    )
    raw_path.write_bytes(base64.b64decode(reply.output_audio.data))
    usage.record("tts")


def _synthesize_edge(script: str, settings: AppSettings, raw_path: Path) -> None:
    import edge_tts

    # Edge speaks at the target speed itself, so the file only needs converting afterwards.
    rate = f"{round((NARRATION_SPEED - 1) * 100):+d}%"
    asyncio.run(edge_tts.Communicate(script, settings.edge_tts_voice, rate=rate).save(str(raw_path)))


def generate_tts_for_project(project_dir: Path, settings: AppSettings) -> Path:
    """Speak the confirmed script and store it as output_1.2x.wav (sped up 1.2x for Shorts pacing)."""
    script = read_final_script(project_dir)
    final = project_dir / TTS_AUDIO_FILENAME
    if settings.tts_provider == "edge":
        raw, tempo, synth = project_dir / "temp_tts_raw.mp3", 1.0, _synthesize_edge
    elif settings.tts_provider == "gemini":
        raw, tempo, synth = project_dir / "temp_tts_raw.wav", NARRATION_SPEED, _synthesize_gemini
    else:
        raise RuntimeError(f"지원하지 않는 음성 엔진입니다: {settings.tts_provider} (gemini 또는 edge)")
    try:
        synth(script, settings, raw)
        retime_audio(raw, final, tempo)
    finally:
        raw.unlink(missing_ok=True)
    return final


# ── timing the script against the audio ─────────────────────────────────────

_NOT_SPOKEN = re.compile(r"[^0-9A-Za-z가-힣]")


def _weight(text: str) -> int:
    return len(_NOT_SPOKEN.sub("", text))


def slice_script_by_segments(script: str, segments: list[dict]) -> list[dict]:
    """Lay the script's words over recognised segments in proportion to how much was said in each.

    Each word goes to the segment covering its midpoint on a shared 0..1 scale, so the script's
    wording is kept exactly and segments that were recognised as nothing are dropped.
    """
    words = script.split()
    total_script = sum(_weight(w) for w in words) or 1
    seg_weights = [max(_weight(s["text"]), 1) for s in segments]
    total_spoken = sum(seg_weights)
    bounds, acc = [], 0
    for w in seg_weights:
        acc += w
        bounds.append(acc / total_spoken)

    buckets: list[list[str]] = [[] for _ in segments]
    done = 0
    seg = 0
    for word in words:
        mid = (done + _weight(word) / 2) / total_script
        while seg < len(bounds) - 1 and mid > bounds[seg]:
            seg += 1
        buckets[seg].append(word)
        done += _weight(word)
    # Proportional placement can strand the first word or two of a new sentence at the end of the previous
    # segment ("…기다립니다. 빛의"); a pause is far likelier at the sentence end, so move them forward.
    for k in range(len(buckets) - 1):
        b = buckets[k]
        ends = [i for i, w in enumerate(b[:-1]) if w.endswith((".", "?", "!"))]
        if ends and 1 <= len(b) - 1 - ends[-1] <= 2:
            cut = ends[-1] + 1
            buckets[k + 1] = b[cut:] + buckets[k + 1]
            buckets[k] = b[:cut]
    return [
        {"text": " ".join(b), "start": round(float(s["start"]), 2), "end": round(float(s["end"]), 2)}
        for b, s in zip(buckets, segments)
        if b
    ]


def _group_into_scenes(blocks: list[dict]) -> list[SceneItem]:
    scenes: list[SceneItem] = []
    current: list[dict] = []
    for block in blocks:
        current.append(block)
        if current[-1]["end"] - current[0]["start"] >= SCENE_GROUP_SECONDS:
            scenes.append(_scene(len(scenes) + 1, current))
            current = []
    if current:
        scenes.append(_scene(len(scenes) + 1, current))
    return scenes


def _scene(scene_id: int, blocks: list[dict]) -> SceneItem:
    start, end = blocks[0]["start"], blocks[-1]["end"]
    return SceneItem(
        scene_id=scene_id, start=start, end=end, duration_frames=int((end - start) * FPS),
        text_blocks=[SceneTextBlock(**b) for b in blocks],
    )


def align_subtitles_and_scenes_for_project(project_dir: Path, settings: AppSettings) -> list[SceneItem]:
    """Recognise the narration (local Whisper), attach the script's wording, save raw_stt + scene_data."""
    from app.references.openai_clients import FasterWhisperClient

    audio = project_dir / TTS_AUDIO_FILENAME
    if not audio.exists():
        raise FileNotFoundError("내레이션 음성이 없습니다. 먼저 음성을 만들어주세요.")
    script = read_final_script(project_dir)
    heard = FasterWhisperClient(settings.whisper_model, settings.whisper_device, "ko").transcribe(audio)["segments"]
    segments = [
        {"text": s["text"].strip(), "start": float(s["start"]), "end": float(s["end"])}
        for s in heard
        if _weight(s.get("text", ""))
    ]
    if not segments:
        raise ValueError("음성에서 말소리를 찾지 못했습니다. 음성을 다시 만들어주세요.")

    write_json(project_dir / RAW_STT_FILENAME, segments)
    blocks = slice_script_by_segments(script, segments)
    for block in blocks:
        block["text"] = digits_for_subtitles(block["text"])  # spelled-out numbers read better as digits on screen
    scenes = _group_into_scenes(blocks)
    write_json(project_dir / SCENE_DATA_FILENAME, [s.model_dump() for s in scenes])
    return scenes
