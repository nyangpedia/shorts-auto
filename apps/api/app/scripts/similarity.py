"""Copy check between our final script and the reference transcript (character 5-gram overlap).
Catches near-verbatim reuse in the same language only; a translated remake shares no n-grams,
so cross-language results are reported as not comparable rather than as "safe"."""
from __future__ import annotations

import re

from app.scripts.models import SimilarityResult, SimilarSentence

N = 5
HIGH, CAUTION, SENTENCE_FLAG = 0.35, 0.15, 0.5


def _norm(text: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", text.lower())


def _grams(text: str) -> set[str]:
    s = _norm(text)
    return {s[i : i + N] for i in range(len(s) - N + 1)}


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]


def _hangul_share(text: str) -> float:
    letters = re.findall(r"[a-zA-Z가-힣]", text)
    return sum("가" <= ch <= "힣" for ch in letters) / len(letters) if letters else 0.0


def check_similarity(final_script: str, reference_script: str) -> SimilarityResult:
    if _hangul_share(reference_script) < 0.5:
        return SimilarityResult(score=0.0, level="비교 불가", comparable=False, sentences=[])
    reference = _grams(reference_script)
    ours = _grams(final_script)
    score = len(ours & reference) / len(ours) if ours else 0.0
    flagged = []
    for sentence in _sentences(final_script):
        grams = _grams(sentence)
        if len(grams) >= 3:
            overlap = len(grams & reference) / len(grams)
            if overlap >= SENTENCE_FLAG:
                flagged.append(SimilarSentence(text=sentence, score=round(overlap, 2)))
    level = "높음" if score >= HIGH else "주의" if score >= CAUTION else "낮음"
    return SimilarityResult(score=round(score, 3), level=level, comparable=True, sentences=flagged)
