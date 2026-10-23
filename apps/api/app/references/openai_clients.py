from __future__ import annotations

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


class FasterWhisperClient:
    def __init__(self, model: str = "base", device: str = "cpu"):
        self.whisper_model = WhisperModel(model, device=device, compute_type="auto")
        self.model_name = model

    def transcribe(self, audio_path: Path) -> dict:
        segments, info = self.whisper_model.transcribe(str(audio_path), language="ko")

        # Convert to Whisper API response format
        text = " ".join(segment.text for segment in segments)
        segments_list = [
            {
                "id": i,
                "seek": int(segment.start * 1000),
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "tokens": [],
                "temperature": 0.0,
                "avg_logprob": -0.5,
                "compression_ratio": 1.5,
                "no_speech_prob": 0.001,
            }
            for i, segment in enumerate(segments)
        ]

        return {
            "task": "transcribe",
            "language": "ko",
            "duration": info.duration,
            "text": text,
            "segments": segments_list,
        }


class AnalysisClient(Protocol):
    def analyze(self, prompt: str) -> dict:
        ...


class OpenAIAnalysisClient:
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("OpenAI API key is missing")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def analyze(self, prompt: str) -> dict:
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            text={"format": {"type": "json_object"}},
        )
        return json.loads(response.output_text)


def write_reference_stt_outputs(project_dir: Path, raw_stt: dict) -> str:
    text = str(raw_stt.get("text", "")).strip()
    write_reference_raw_stt(project_dir, raw_stt)
    write_reference_script(project_dir, f"{text}\n")
    return text
