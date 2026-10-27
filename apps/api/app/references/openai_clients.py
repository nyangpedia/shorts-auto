from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import json
from typing import Protocol

import logging
from types import SimpleNamespace

from openai import APIConnectionError, APIStatusError, NotFoundError, OpenAI, RateLimitError
from faster_whisper import WhisperModel

from app.core import usage
from app.references.files import write_reference_raw_stt, write_reference_script

logger = logging.getLogger(__name__)


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


class FallbackLLM:
    """OpenAI-compatible chat client that moves to the next model when one fails.

    Gemini's free tier caps each model separately (~20 requests/day), so falling through
    a list of models multiplies the daily budget.
    """

    _RETRYABLE = (RateLimitError, NotFoundError, APIConnectionError)

    def __init__(self, api_key: str, base_url: str = "", fallbacks: list[str] | None = None):
        # max_retries=0: on a quota 429 the SDK would otherwise sleep and retry the same model.
        self._client = OpenAI(api_key=api_key, base_url=base_url or None, max_retries=0, timeout=180.0)
        self._fallbacks = fallbacks or []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, *, model: str, **kwargs):
        models = [model] + [m for m in self._fallbacks if m != model]
        for i, name in enumerate(models):
            try:
                response = self._client.chat.completions.create(model=name, **kwargs)
                usage.record("llm")
                return response
            except APIStatusError as exc:
                retryable = isinstance(exc, self._RETRYABLE) or exc.status_code >= 500
                if not retryable or i == len(models) - 1:
                    raise
                logger.warning("LLM %s failed (%s); falling back to %s", name, exc.status_code, models[i + 1])
            except APIConnectionError as exc:
                if i == len(models) - 1:
                    raise
                logger.warning("LLM %s failed (%s); falling back to %s", name, type(exc).__name__, models[i + 1])


def make_llm_client(settings) -> FallbackLLM:
    return FallbackLLM(settings.llm_api_key, settings.llm_base_url, settings.llm_fallback_list)


class AnalysisClient(Protocol):
    def analyze(self, prompt: str) -> dict:
        ...


class OpenAIAnalysisClient:
    def __init__(self, api_key: str, model: str, base_url: str = "", fallbacks: list[str] | None = None):
        if not api_key:
            raise ValueError("LLM API key is missing")
        self.client = FallbackLLM(api_key, base_url, fallbacks)
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
