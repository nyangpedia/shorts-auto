"""Script models, files and prompts, without the HTTP layer."""
from pathlib import Path

import pytest

from app.scripts.files import FINAL_SCRIPT_FILE, SCRIPT_CANDIDATES_FILE, read_script_state, write_final_script_state, write_script_candidates, write_selected_script_candidate
from app.scripts.generation import build_candidate_generation_prompt, build_final_script_prompt, validate_candidate_payload, validate_final_script
from app.scripts.models import FinalScriptState, ScriptCandidate, SelectScriptCandidateRequest, TtsValidationResult


def draft(candidate_id: str = "draft_a", kind: str = "draft_a", **overrides) -> ScriptCandidate:
    fields = dict(
        candidate_id=candidate_id, candidate_type=kind, title="돈을 모으는 이상한 습관",
        hook="돈을 못 모으는 사람은 이것부터 틀립니다.", target_viewer="저축이 어려운 사회초년생",
        why_it_can_work="첫 문장이 자기 문제처럼 들립니다.", main_curiosity_question="왜 아껴도 돈이 안 모일까?",
        structure_summary="상식 흔들기, 원인, 반전, 결론.", draft_script="돈을 못 모으는 건 의지 문제가 아닙니다.",
        borrowed_reference_structure="상식 반박형 훅을 빌립니다.",
    )
    return ScriptCandidate(**{**fields, **overrides})


# ── models ──

def test_blank_fields_are_rejected():
    with pytest.raises(ValueError):
        draft(title="")
    with pytest.raises(ValueError):
        SelectScriptCandidateRequest(candidate_id="   ")
    with pytest.raises(ValueError):
        TtsValidationResult(is_valid=False, issues=[""])


@pytest.mark.parametrize("payload", [{"is_valid": True, "issues": ["English letters remain"]}, {"is_valid": False, "issues": []}])
def test_tts_verdict_must_match_issues(payload):
    with pytest.raises(ValueError):
        TtsValidationResult(**payload)


# ── files ──

def test_markdown_alone_is_not_a_confirmed_script(tmp_path: Path):
    (tmp_path / FINAL_SCRIPT_FILE).write_text("orphan markdown\n", encoding="utf-8")
    state = read_script_state(tmp_path)
    assert state.final_script is None and state.tts_validation is None


def test_saved_state_reads_back(tmp_path: Path):
    drafts = [draft("draft_a", "draft_a"), draft("draft_b", "draft_b")]
    write_script_candidates(tmp_path, drafts)
    write_selected_script_candidate(tmp_path, drafts[1])
    write_final_script_state(tmp_path, FinalScriptState(
        selected_candidate_id="draft_b", feedback="조금 더 강하게", final_script="돈을 못 모으는 이유는 의지가 아닙니다.",
        tts_validation=TtsValidationResult(is_valid=True, issues=[]),
    ))

    state = read_script_state(tmp_path)
    assert (tmp_path / SCRIPT_CANDIDATES_FILE).exists()
    assert (tmp_path / FINAL_SCRIPT_FILE).read_text(encoding="utf-8") == "돈을 못 모으는 이유는 의지가 아닙니다.\n"
    assert len(state.candidates) == 2
    assert state.selected_candidate.candidate_id == "draft_b"
    assert state.final_script == "돈을 못 모으는 이유는 의지가 아닙니다."
    assert state.tts_validation.is_valid is True


# ── prompts and model replies ──

def test_draft_prompt_carries_the_reference():
    prompt = build_candidate_generation_prompt(reference_script="레퍼런스 대본", reference_analysis={"primary_structure": "상식 반박"})
    for needle in ["exactly two", "Draft A", "Draft B", "레퍼런스 대본", "체감 단위 환산"]:
        assert needle in prompt, needle


def test_reply_with_two_drafts():
    reply = {"candidates": [draft("draft_a", "draft_a").model_dump(), draft("draft_b", "draft_b").model_dump()]}
    assert [c.candidate_id for c in validate_candidate_payload(reply)] == ["draft_a", "draft_b"]


def test_reply_with_extra_items_keeps_the_drafts():
    reply = {"candidates": [draft(f"x{i}", "same_topic" if i == 0 else "different_topic").model_dump() for i in range(4)]}
    reply["candidates"][2]["candidate_type"] = "draft_b"
    reply["candidates"][3]["candidate_type"] = "draft_a"
    assert [c.candidate_type for c in validate_candidate_payload(reply)] == ["draft_b", "draft_a"]


def test_reply_with_one_draft_is_rejected():
    with pytest.raises(ValueError, match="두 개"):
        validate_candidate_payload({"candidates": [draft().model_dump()]})


def test_final_prompt_has_feedback_and_tts_rules():
    prompt = build_final_script_prompt(selected_candidate=draft(), feedback="더 날카롭게")
    for needle in [
        "더 날카롭게",
        "all numbers are written in Korean pronunciation",
        "percent signs are written as 퍼센트",
        "parentheses and brackets are removed",
        "English words and acronyms are written by Korean pronunciation",
    ]:
        assert needle in prompt, needle


def test_tts_check_flags_what_a_voice_would_misread():
    result = validate_final_script("AI가 24% 성장했습니다. (테스트)")
    assert result.is_valid is False
    assert {"English letters remain", "Arabic numerals remain", "Percent symbol remains", "Bracket characters remain"} <= set(result.issues)


def test_tts_check_passes_spoken_korean():
    result = validate_final_script("에이아이가 이십사 퍼센트 성장했습니다.")
    assert (result.is_valid, result.issues) == (True, [])
