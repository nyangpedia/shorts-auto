from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import json
from typing import Protocol

from openai import OpenAI
from faster_whisper import WhisperModel

from app.references.files import write_reference_raw_stt, write_reference_script


class TranscriptionClient(Protocol):
    def transcribe(self, audio_path: Path) -> dict:
        ...


class OpenAITranscriptionClient:
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("OpenAI API key is missing")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def transcribe(self, audio_path: Path) -> dict:
        with audio_path.open("rb") as audio_file:
            result = self.client.audio.transcriptions.create(
                model=self.model,
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
        if hasattr(result, "model_dump"):
            return result.model_dump()
        return dict(result)


@lru_cache(maxsize=2)
def _load_whisper(model: str, device: str) -> WhisperModel:
    return WhisperModel(model, device=device, compute_type="auto")


class FasterWhisperClient:
    def __init__(self, model: str = "base", device: str = "cpu"):
        self.whisper_model = _load_whisper(model, device)

    def transcribe(self, audio_path: Path) -> dict:
        segments, info = self.whisper_model.transcribe(str(audio_path), language="ko")
        segments_list = [
            {"id": i, "start": s.start, "end": s.end, "text": s.text}
            for i, s in enumerate(segments)
        ]
        return {
            "task": "transcribe",
            "language": "ko",
            "duration": info.duration,
            "text": " ".join(seg["text"].strip() for seg in segments_list),
            "segments": segments_list,
        }


class AnalysisClient(Protocol):
    def analyze(self, prompt: str) -> dict:
        ...


class OpenAIAnalysisClient:
    def __init__(self, api_key: str, model: str, base_url: str = ""):
        if not api_key:
            raise ValueError("LLM API key is missing")
        self.client = OpenAI(api_key=api_key, base_url=base_url or None)
        self.model = model
        self.base_url = base_url

    def analyze(self, prompt: str) -> dict:
        # JSON mode is OpenAI-only; other OpenAI-compatible providers get fence stripping instead.
        extra = {} if self.base_url else {"response_format": {"type": "json_object"}}
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            **extra,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(content)


def write_reference_stt_outputs(project_dir: Path, raw_stt: dict) -> str:
    text = str(raw_stt.get("text", "")).strip()
    write_reference_raw_stt(project_dir, raw_stt)
    write_reference_script(project_dir, f"{text}\n")
    return text
