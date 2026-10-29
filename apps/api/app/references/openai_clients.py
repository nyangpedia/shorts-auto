"""Speech-to-text and LLM clients.

Free path: local faster-whisper for speech, Gemini (OpenAI-compatible endpoint) for text, falling
through several Gemini models because each has its own small daily cap. OpenAI works when keyed.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol

from faster_whisper import WhisperModel
from openai import APIConnectionError, APIStatusError, NotFoundError, OpenAI, RateLimitError

from app.core import usage
from app.references.files import write_reference_raw_stt, write_reference_script

logger = logging.getLogger(__name__)


class TranscriptionClient(Protocol):
    def transcribe(self, audio_path: Path) -> dict: ...


class AnalysisClient(Protocol):
    def analyze(self, prompt: str) -> dict: ...


# ── speech to text ──────────────────────────────────────────────────────────

class OpenAITranscriptionClient:
    """Paid Whisper API; returns OpenAI's verbose JSON (text + timed segments)."""

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("OpenAI API key is missing")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def transcribe(self, audio_path: Path) -> dict:
        with audio_path.open("rb") as audio:
            reply = self.client.audio.transcriptions.create(
                model=self.model, file=audio, response_format="verbose_json", timestamp_granularities=["segment"],
            )
        return reply.model_dump() if hasattr(reply, "model_dump") else dict(reply)


@lru_cache(maxsize=2)
def _load_whisper(model: str, device: str) -> WhisperModel:
    return WhisperModel(model, device=device, compute_type="auto")


class FasterWhisperClient:
    """Local Whisper on CPU, in the same shape as the OpenAI reply."""

    def __init__(self, model: str = "base", device: str = "cpu", language: str | None = None):
        # None = auto-detect (references can be foreign); our own narration passes "ko".
        self.whisper_model = _load_whisper(model, device)
        self.language = language

    def transcribe(self, audio_path: Path) -> dict:
        found, info = self.whisper_model.transcribe(str(audio_path), language=self.language)
        segments = [{"id": n, "start": s.start, "end": s.end, "text": s.text} for n, s in enumerate(found)]
        return {
            "task": "transcribe",
            "language": info.language,
            "duration": info.duration,
            "text": " ".join(s["text"].strip() for s in segments),
            "segments": segments,
        }


def write_reference_stt_outputs(project_dir: Path, raw_stt: dict) -> str:
    """Save the raw recognition result and its plain text as the reference script."""
    text = str(raw_stt.get("text", "")).strip()
    write_reference_raw_stt(project_dir, raw_stt)
    write_reference_script(project_dir, text + "\n")
    return text


# ── text generation ─────────────────────────────────────────────────────────

class FallbackLLM:
    """OpenAI-compatible chat client that moves to the next model when one fails.

    Gemini's free tier caps each model separately (~20 requests/day), so falling through
    a list of models multiplies the daily budget.
    """

    _TRY_NEXT = (RateLimitError, NotFoundError, APIConnectionError)

    def __init__(self, api_key: str, base_url: str = "", fallbacks: list[str] | None = None):
        # max_retries=0: on a quota 429 the SDK would otherwise sleep and retry the same model.
        self._client = OpenAI(api_key=api_key, base_url=base_url or None, max_retries=0, timeout=180.0)
        self._fallbacks = fallbacks or []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, *, model: str, **kwargs):
        chain = [model, *(m for m in self._fallbacks if m != model)]
        for position, name in enumerate(chain):
            last = position == len(chain) - 1
            try:
                reply = self._client.chat.completions.create(model=name, **kwargs)
            except APIStatusError as exc:
                if last or not (isinstance(exc, self._TRY_NEXT) or exc.status_code >= 500):
                    raise  # a bad request fails the same way on every model
                logger.warning("LLM %s failed (%s); falling back to %s", name, exc.status_code, chain[position + 1])
            except APIConnectionError as exc:
                if last:
                    raise
                logger.warning("LLM %s failed (%s); falling back to %s", name, type(exc).__name__, chain[position + 1])
            else:
                usage.record("llm")
                return reply


def make_llm_client(settings) -> FallbackLLM:
    return FallbackLLM(settings.llm_api_key, settings.llm_base_url, settings.llm_fallback_list)


class OpenAIAnalysisClient:
    """Sends one prompt, returns the reply parsed as JSON."""

    def __init__(self, api_key: str, model: str, base_url: str = "", fallbacks: list[str] | None = None):
        if not api_key:
            raise ValueError("LLM API key is missing")
        self.client = FallbackLLM(api_key, base_url, fallbacks)
        self.model = model
        self.base_url = base_url

    def analyze(self, prompt: str) -> dict:
        # JSON mode is OpenAI-only; other OpenAI-compatible providers get fence stripping instead.
        json_mode = {} if self.base_url else {"response_format": {"type": "json_object"}}
        reply = self.client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": prompt}], **json_mode)
        text = reply.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(text)

    def describe(self, content: list[dict]) -> str:
        """Free-text reply to a message with text and image parts (Gemini reads images on the free tier)."""
        reply = self.client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": content}])
        return reply.choices[0].message.content or ""
