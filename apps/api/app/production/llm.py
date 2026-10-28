"""One JSON-returning LLM call, shared by scene planning and prompt revision."""
from __future__ import annotations

import json
import re

from app.core.settings import AppSettings
from app.references.openai_clients import make_llm_client

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def ask_json(settings: AppSettings, prompt: str, temperature: float = 0.3) -> dict:
    reply = make_llm_client(settings).chat.completions.create(
        model=settings.openai_analysis_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    text = _FENCE.sub("", reply.choices[0].message.content.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"AI 응답을 읽지 못했습니다 (JSON 형식 아님): {text[:200]}") from exc
