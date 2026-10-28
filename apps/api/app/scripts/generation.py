"""Script writing prompts: two drafts from a reference's formula, then one narration ready for TTS."""
from __future__ import annotations

import json
import re

from pydantic import ValidationError

from app.scripts.models import (
    FINAL_SCRIPT_MAX_LENGTH,
    FactCheckClaim,
    FactCheckResult,
    FinalScriptState,
    ScriptCandidate,
    TtsValidationResult,
    clean_text,
)

# Words in the user's note that mean "make the reference's own subject again, better".
_REMAKE_WORDS = ("원본", "원작", "리메이크", "동일 주제", "재구성", "원복", "스크립트 참고", "대본 참고")
_TOPIC_NUMBER = re.compile(r"#?\s*([1-5])\s*번")


def _topic_brief(analysis: dict, note: str) -> tuple[str, str]:
    """What the drafts are about, and how the reference script may be used. Returns (brief, reference_use)."""
    topics = analysis.get("recommended_topics") or []
    picked_number = int(m.group(1)) if (m := _TOPIC_NUMBER.search(note)) else None
    picked = next((t for t in topics if t.get("topic_number") == picked_number), None)

    if any(w in note for w in _REMAKE_WORDS) or picked_number == 1:
        return (
            f"[주제] 레퍼런스와 같은 소재를 사실을 보강해 더 강하게 다시 만든다.\n[사용자 요청] {note or '없음'}\n"
            "- 요청에 시작 멘트나 특정 대사가 있으면 도입부에 그대로 넣는다. 전개 순서나 관점 지시도 빠짐없이 따른다.",
            "소재와 핵심 사실을 가져와도 되는 원본",
        )
    if picked:
        return (
            f"[주제] {picked.get('title')} (분류: {picked.get('category')})\n"
            f"- 추천 훅: {picked.get('hook')}\n- 끝까지 보게 할 질문: {picked.get('core_question')}\n"
            f"- 제작 방향: {picked.get('production_strategy')}\n[사용자 추가 요청] {note or '없음'}\n"
            "- 두 초안 모두 이 주제만 다룬다. 레퍼런스의 소재·사례·결론은 한 문장도 가져오지 않는다.",
            "문장 호흡과 긴장 구조만 참고하는 견본 — 내용은 쓰지 말 것",
        )
    if note:
        return (
            f"[주제와 요청] {note}\n- 두 초안 모두 이 요청의 주제만 다룬다. 요청한 시작 대사·전개·숫자는 빠짐없이 반영한다.",
            "호흡과 구조를 참고하는 견본",
        )
    return (
        "[주제] 분석의 추천 주제 중 상식과 가장 세게 부딪히고 파급력이 큰 것 하나를 골라, 두 초안 모두 그 주제로 쓴다.",
        "호흡과 구조를 참고하는 견본",
    )


def build_candidate_generation_prompt(reference_script: str, reference_analysis: dict, user_feedback: str = "") -> str:
    analysis = reference_analysis if isinstance(reference_analysis, dict) else {}
    brief, reference_use = _topic_brief(analysis, user_feedback.strip())
    return f"""너는 한국 유튜브 쇼츠 기획자이자 지식 콘텐츠 팩트체커다. Write exactly two Korean narration drafts, Draft A and Draft B, on the same topic.
레퍼런스가 왜 터졌는지 분석한 내용을 바탕으로, 새 쇼츠 대본 초안 두 개를 쓴다.

{brief}

[가장 먼저 지킬 것: 정확성]
- 학계나 공식 기관에서 정설인 내용만 "~입니다"처럼 단정한다.
- 가설·소수 의견·논쟁 중인 주장은 "일부 학자들은 ~라고 봅니다", "~라는 가설도 있습니다"처럼 성격을 밝힌다. 정설을 "거짓말", "다 틀렸다"로 몰지 않는다.
- 확실히 아는 숫자만 쓴다. 어림값은 "약", "~정도"를 붙이고, 자극을 위해 숫자를 키우지 않는다.
- 상식을 뒤집는 훅도 사실을 비틀지 않는 선에서만 쓴다. 자신이 없으면 "정말 그럴까요?" 같은 질문으로 연다.

[내용 밀도]
- "엄청나다", "놀랍다" 같은 빈 형용사 대신, 작동 원리와 정밀한 숫자가 들어간 구체적 사실을 두 개 이상 넣는다.
- 큰 양이나 규모는 머릿속에 바로 그려지는 일상 단위로 바꿔 말한다(체감 단위 환산): 올림픽 수영장 몇 개, 63빌딩 몇 채, 서울 면적의 몇 배, 종이컵 몇 잔처럼.

[흐름 — 약 50초]
1. 0~3초: 시청자가 당연하다고 믿는 것을 한 문장으로 흔들어 스크롤을 멈추게 한다.
2. 3~15초: 예상 못 한 질문이나 관찰 포인트로 "왜?"를 키운다.
3. 15~35초: "더 놀라운 건…", "여기서 반전이…"처럼 국면을 바꾸며 사실과 원리를 쉬지 않고 풀어낸다. 설명조로 늘어지지 않는다.
4. 35~50초: 큰 숫자와 환산으로 깨달음을 주고, 댓글이나 공유를 부르는 한마디로 끝낸다.

[분량과 말투]
- draft_script는 공백 포함 420~520자, 8~10문장. 250~350자처럼 짧으면 내용이 비니 안 된다.
- 바로 옆에서 말해 주는 구어체("~거든요", "~죠?", "~다니까요"). 백과사전 문장은 쓰지 않는다.

[두 초안의 차이 — 주제는 같고 연출만 다르다]
- Draft A (candidate_id "draft_a", candidate_type "draft_a"): 빠른 템포의 충격형. 흔한 오해를 짚고 검증된 사실과 환산 숫자로 연달아 뒤집는다.
- Draft B (candidate_id "draft_b", candidate_type "draft_b"): 스토리형. 작은 관찰이나 실험에서 시작해 단계적으로 커지는 비밀과 반전으로 끌고 간다.

[업로드용 정보]
- title_options: 서로 다른 세 가지 제목 — 호기심형("…는 얼마일까?"), 숫자·충격형("…가 63빌딩 150채?"), 상식 파괴형("기껏해야 …? 진짜는 …").
- title: 셋 중 가장 강한 하나.
- description: 내용을 2~3줄로 요약한 평문. 별표(**)와 따옴표는 쓰지 않는다.
- tags: "#키워드 #키워드 #쇼츠"처럼 공백으로 구분한 해시태그.
- keywords: "키워드, 키워드, 키워드, 키워드"처럼 쉼표로 구분.

[출력] 설명 없이 JSON 하나만. candidates 배열에 초안 두 개를 넣고, 각 초안은 다음 키를 모두 가진다:
candidate_id, candidate_type, title, title_options(3개), description, tags, keywords,
hook(첫 3초 대사), target_viewer, why_it_can_work, main_curiosity_question,
structure_summary(훅→궁금증→국면 전환→보상 흐름 요약), draft_script(내레이션 전문), borrowed_reference_structure(레퍼런스에서 가져온 구조 설명).

[레퍼런스 분석]
{json.dumps(analysis, ensure_ascii=False, indent=1)}

[레퍼런스 대본 — {reference_use}]
{reference_script}"""


def build_final_script_prompt(selected_candidate: ScriptCandidate, feedback: str = "") -> str:
    draft = selected_candidate.model_dump() if hasattr(selected_candidate, "model_dump") else selected_candidate
    return f"""Turn the chosen draft below into the one final Korean narration that a TTS voice will read.
고른 초안을 음성 합성이 정확하고 맛깔나게 읽을 최종 낭독 대본으로 다듬어라.

[지킬 것]
- 초안의 사실, 숫자, 환산 비유, 흐름(훅 → 궁금증 → 국면 전환 → 보상)을 줄이거나 빼지 않는다. 분량은 공백 포함 400~520자.
- 초안에서 가설을 정설처럼 단정한 곳이 있으면 "~라는 주장도 있습니다"처럼 고친다. 새 사실이나 숫자를 만들어 넣지 않는다.
- 말하듯 자연스러운 문장으로 다듬고, 쉼표와 마침표로 숨 쉴 곳과 힘줄 곳을 만든다.

[음성 합성 규칙 — 반드시]
- all numbers are written in Korean pronunciation: 160억 → 백육십억, 6,400개 → 육천사백 개, 6개 → 여섯 개, 30번 → 서른 번, 1/25 → 이십오분의 일, 150m → 백오십 미터.
- percent signs are written as 퍼센트: 99% → 구십구 퍼센트.
- parentheses and brackets are removed.
- English words and acronyms are written by Korean pronunciation: AI → 에이아이, DNA → 디엔에이.
- 최종 대본에 아라비아 숫자, %, 영어 알파벳이 하나도 남으면 안 된다.

[사용자 요청]
{feedback.strip() or "없음"}

[고른 초안]
{json.dumps(draft, ensure_ascii=False, indent=1)}

설명 없이 JSON 하나만 출력한다: {{"final_script": "..."}}"""


def validate_candidate_payload(payload: dict) -> list[ScriptCandidate]:
    """The two drafts from a generation reply (draft_a/draft_b first if the model added extras)."""
    items = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise ValueError("AI 응답에 candidates 목록이 없습니다.")
    try:
        candidates = [ScriptCandidate.model_validate(item) for item in items]
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    drafts = [c for c in candidates if c.candidate_type in ("draft_a", "draft_b")] or candidates
    if len(drafts) < 2:
        raise ValueError(f"초안이 두 개 필요한데 {len(drafts)}개만 왔습니다.")
    return drafts[:2]


def extract_final_script(payload: dict) -> str:
    script = payload.get("final_script") if isinstance(payload, dict) else None
    if not isinstance(script, str):
        raise ValueError("AI 응답에 final_script가 없습니다.")
    return clean_text(script, "final_script", FINAL_SCRIPT_MAX_LENGTH)


_TTS_PROBLEMS = (
    (re.compile(r"[A-Za-z]"), "English letters remain"),
    (re.compile(r"\d"), "Arabic numerals remain"),
    (re.compile(r"%"), "Percent symbol remains"),
    (re.compile(r"[()\[\]{}]"), "Bracket characters remain"),
)


def validate_final_script(script: str) -> TtsValidationResult:
    issues = [label for pattern, label in _TTS_PROBLEMS if pattern.search(script)]
    return TtsValidationResult(is_valid=not issues, issues=issues)


def build_final_script_state(selected_candidate_id: str, feedback: str, final_script: str) -> FinalScriptState:
    script = final_script.strip()
    return FinalScriptState(
        selected_candidate_id=selected_candidate_id,
        feedback=feedback.strip(),
        final_script=script,
        tts_validation=validate_final_script(script),
    )


def build_fact_check_prompt(script: str) -> str:
    return f"""
당신은 꼼꼼한 한국어 팩트체커입니다. 아래 유튜브 쇼츠 내레이션 대본에서 **사실 주장**(숫자, 역사적 사건, 과학적 설명, 인과관계 단정)을 모두 찾아 하나씩 판정하세요.
의견·감탄·질문은 제외합니다. 검색 도구가 없으니 당신의 지식으로 판단하되, 확신이 없으면 "의심"으로 표시하세요. 모르는 것을 확실하다고 하지 마세요.

판정 기준:
- "확실": 학계·공식 기관에서 널리 받아들여진 사실이고 숫자도 맞음
- "논란": 소수설·가설·학자 간 논쟁이 있는데 대본이 정설처럼 단정함
- "의심": 틀렸거나, 숫자가 부풀려졌거나, 확인이 어려운 주장

반드시 JSON만 반환하세요:
{{
  "claims": [
    {{
      "quote": "대본에서 그대로 복사한 해당 구절 (글자 하나도 바꾸지 말 것, 30자 이내 권장)",
      "verdict": "확실 | 논란 | 의심",
      "reason": "판정 이유 한두 문장. 논란·의심이면 정설이나 올바른 수치를 함께 적을 것",
      "search_query": "사람이 직접 확인할 때 쓸 한국어 검색어"
    }}
  ]
}}

대본:
{script.strip()}
""".strip()


def parse_fact_check(payload: dict, script: str) -> FactCheckResult:
    from app.scripts.files import script_hash

    claims = []
    for item in payload.get("claims", []) if isinstance(payload, dict) else []:
        try:
            claims.append(FactCheckClaim.model_validate(item))
        except ValidationError:
            continue  # one malformed claim shouldn't discard the rest
    order = {"의심": 0, "논란": 1, "확실": 2}
    claims.sort(key=lambda c: order[c.verdict])
    return FactCheckResult(script_hash=script_hash(script), claims=claims)
