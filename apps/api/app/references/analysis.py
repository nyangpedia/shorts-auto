"""Why did the reference Short work? The analysis prompt, its response schema, and the readable report."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.references.files import write_reference_analysis_files


# ── response schema (field names are the stored format of existing projects) ──

class AnalysisSection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    section: str = Field(min_length=1)
    script_excerpt: str = Field(min_length=1)
    viewer_reaction: str = Field(min_length=1)
    purpose: str = Field(min_length=1)


class SentenceAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sentence_range: str = ""
    script_text: str = ""
    viewer_mindset: str = ""
    technique: str = ""
    role: str = ""


class RecommendedTopic(BaseModel):
    model_config = ConfigDict(extra="ignore")

    topic_number: int = 1
    title: str = ""
    category: str = ""
    formula: str = ""
    hook: str = ""
    core_question: str = ""
    production_strategy: str = ""


def _as_text_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, dict):  # some models name the items: {"subject": "...", "payoff": "..."}
        return [str(item) for item in value.values()]
    raise ValueError(f"문자열이나 문자열 목록이어야 합니다 (받은 값: {type(value).__name__})")


class ReferenceAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    primary_structure: str = Field(min_length=1)
    supporting_structures: list[str] = Field(default_factory=list)
    winning_formula: str = ""
    viral_reasons: list[str] = Field(default_factory=list)
    thinking_vs_payoff: str = ""
    hook_analysis: str = Field(min_length=1)
    curiosity_gap: str = Field(min_length=1)
    retention_analysis: str = Field(min_length=1)
    payoff_analysis: str = Field(min_length=1)
    risk_notes: list[str] = Field(default_factory=list)
    reusable_structure_notes: str = Field(min_length=1)
    section_breakdown: list[AnalysisSection] = Field(default_factory=list)
    sentence_analyses: list[SentenceAnalysis] = Field(default_factory=list)
    recommended_topics: list[RecommendedTopic] = Field(default_factory=list)

    _lists = field_validator("supporting_structures", "risk_notes", "viral_reasons", mode="before")(
        classmethod(lambda cls, value: _as_text_list(value))
    )


def validate_reference_analysis(analysis: dict) -> dict:
    try:
        return ReferenceAnalysis.model_validate(analysis).model_dump()
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


# ── prompt ──────────────────────────────────────────────────────────────────

# Hook patterns that keep showing up in Shorts that travel; the model names the one(s) this video uses.
HOOK_PATTERNS = [
    "상식 뒤집기 — 당연한 줄 알았던 것이 반대라고 말한다",
    "직접 확인 — 정말 그런지 실험하거나 검증해 보인다",
    "정체 공개 — 처음엔 무엇인지 모를 것을 보여 주고 마지막에 밝힌다",
    "조건 걸기 — 어려운 제약을 두고 성공할지 지켜보게 한다",
    "변신 — 처음과 끝의 상태가 크게 달라진다",
    "해결 — 시청자가 겪는 불편을 풀어 준다",
    "견주기 — 둘 이상을 비교하거나 순위를 매긴다",
    "점점 세게 — 단계마다 더 큰 것이 나온다",
    "내 얘기 — 시청자가 자기 상황이라고 느끼는 장면",
    "알고 보니 — 첫인상과 정반대의 결말",
    "보는 맛 — 과정 자체가 만족스럽다",
    "맞혀 보기 — 시청자가 답을 예측하고 확인하게 한다",
]


def build_analysis_prompt(reference_script: str) -> str:
    patterns = "\n".join(f"  - {p}" for p in HOOK_PATTERNS)
    return f"""Explain why viewers stop, why they keep watching, and where they feel payoff — then turn it into a plan for new videos.
너는 쇼츠 성과를 분석하는 기획 컨설턴트다. 아래 레퍼런스 쇼츠 대본이 왜 조회수가 높았는지 풀어 보고,
같은 공식으로 새 영상을 만들 수 있게 정리해라. 모든 내용은 크리에이터가 바로 쓸 수 있게 구체적인 한국어로 쓴다.

[보는 관점]
- 많이 퍼지는 쇼츠의 훅 유형 (이 영상이 어떤 것에 해당하는지 고른다):
{patterns}
- 잘 되는 쇼츠의 공통점: 익숙한 대상에 낯선 조건을 붙인다 / 설명보다 사건·현상이 먼저 나온다 /
  시청자가 결과를 스스로 예측하게 만든다 / 중간에 상황이 크게 바뀐다 /
  시청자가 해야 하는 생각의 양보다 확인하고 싶은 결과가 훨씬 선명하다.

[채울 항목 — JSON 키 (형태)]
- primary_structure (문자열): 이 영상의 핵심 구조 한두 문장
- supporting_structures (문자열 배열): 함께 쓰인 보조 장치
- winning_formula (문자열): 위 훅 유형 중 주된 것의 이름
- viral_reasons (문자열 4개 배열): 퍼진 이유 — 소재와 낯선 조건의 결합 / 사건을 먼저 둔 배치 / 중반 이탈을 막은 변화 / 결말 보상
- thinking_vs_payoff (문자열): 시청자가 들여야 하는 생각 대비 얻는 결과의 선명함
- hook_analysis (문자열): 첫 3초가 스크롤을 멈추게 한 원리
- curiosity_gap (문자열): 끝까지 보게 만든 궁금증
- retention_analysis (문자열): 중반을 붙잡은 전개 장치와 리듬
- payoff_analysis (문자열): 결말의 보상과 공유하고 싶어지는 지점
- risk_notes (문자열 배열): 따라 만들 때 빠지기 쉬운 함정
- reusable_structure_notes (문자열): 다른 소재로 옮길 때 그대로 가져갈 뼈대
- section_breakdown (객체 배열): 구간마다 {{section, script_excerpt, viewer_reaction, purpose}}
- sentence_analyses (객체 배열): 대본 전체를 1~3문장씩 끊어 {{sentence_range, script_text, viewer_mindset(시청자 속마음), technique, role(소재 이해 / 후킹 / 의문 심화 / 반전 / 결말 보상 중 하나)}}
- recommended_topics (객체 5개 배열): {{topic_number(숫자), title, category, formula, hook(첫 문장), core_question, production_strategy}}
  · 5개 모두 레퍼런스와 같은 분야(채널 주제) 안에서 고른다. 무관한 분야로 벗어나지 않는다.
  · category는 다음 이름 중 하나를 글자 그대로 쓴다(앞뒤에 분야명 등을 붙이지 않는다): 원작 리메이크 / 상식 파괴 / 미스터리·비하인드 / 실패·경고 / 비교·랭킹 / 실전 꿀팁
  · 1번은 category "원작 리메이크": 같은 소재를 사실을 보강해 더 강하게.
  · 2~5번은 같은 분야의 서로 다른 소재를, 서로 다른 각도로: 상식 파괴 / 미스터리·비하인드 / 실패·경고 / 비교·랭킹 / 실전 꿀팁 중에서 겹치지 않게.
    원본이나 다른 추천과 핵심 사실·사례·결론이 겹치면 안 된다.
  · production_strategy에는 누가 관심을 갖는지, 중간에 무엇이 바뀌는지, 끝에 무엇을 얻는지를 쓴다.

설명이나 마크다운 없이 위 키를 가진 JSON 하나만 출력한다.

[레퍼런스 대본]
{reference_script}"""


# ── readable report ─────────────────────────────────────────────────────────

def _cell(text: Any) -> str:
    return str(text or "").replace("|", "/").replace("\n", " ")


def render_analysis_markdown(analysis: dict) -> str:
    a = validate_reference_analysis(analysis)
    out = [
        "# Reference Analysis — 이 쇼츠는 왜 퍼졌나",
        "",
        "## 1. 성공 공식",
        f"- **주된 공식:** {a['winning_formula'] or a['primary_structure']}",
    ]
    if a["supporting_structures"]:
        out.append(f"- **함께 쓴 장치:** {', '.join(a['supporting_structures'])}")
    if a["thinking_vs_payoff"]:
        out.append(f"- **생각할 거리 대비 보상:** {a['thinking_vs_payoff']}")
    if a["viral_reasons"]:
        out += ["", "### 퍼진 이유", *[f"- {r}" for r in a["viral_reasons"]]]
    out += [
        "",
        f"- **멈춘 이유 (훅):** {a['hook_analysis']}",
        f"- **계속 본 이유 (궁금증):** {a['curiosity_gap']}",
        f"- **중반을 붙잡은 장치:** {a['retention_analysis']}",
        f"- **끝의 보상:** {a['payoff_analysis']}",
        "",
        "### 다른 소재로 옮길 뼈대",
        a["reusable_structure_notes"],
    ]
    if a["risk_notes"]:
        out += ["", "### 주의할 점", *[f"- {r}" for r in a["risk_notes"]]]

    if a["sentence_analyses"]:
        out += ["", "---", "", "## 2. 문장별 시청자 심리", "",
                "| 구간 | 역할 | 대본 | 시청자 속마음 | 쓰인 기법 |", "|---|---|---|---|---|"]
        out += [f"| {_cell(s['sentence_range'])} | **{_cell(s['role'])}** | {_cell(s['script_text'])} | *\"{_cell(s['viewer_mindset'])}\"* | {_cell(s['technique'])} |"
                for s in a["sentence_analyses"]]
    elif a["section_breakdown"]:
        out += ["", "---", "", "## 2. 구간별 분석"]
        for s in a["section_breakdown"]:
            out += [f"### {s['section']}", f"- **대본:** {s['script_excerpt']}", f"- **시청자 반응:** {s['viewer_reaction']}",
                    f"- **의도:** {s['purpose']}", ""]

    if a["recommended_topics"]:
        out += ["", "---", "", "## 3. 이 공식으로 만들 새 주제 5가지",
                "> 마음에 드는 주제를 고르거나 원하는 방향을 적으면, 그걸로 대본 초안 2개를 만듭니다.", ""]
        for t in a["recommended_topics"]:
            out += [f"### #{t['topic_number']}. {t['title']} `[{t['category']}]`", f"- **공식:** {t['formula']}",
                    f"- **첫 문장:** \"{t['hook']}\"", f"- **끝까지 보게 할 질문:** {t['core_question']}",
                    f"- **제작 방향:** {t['production_strategy']}", ""]
    return "\n".join(out).strip() + "\n"


def write_reference_analysis(project_dir: Path, analysis: dict) -> str:
    analysis = validate_reference_analysis(analysis)
    markdown = render_analysis_markdown(analysis)
    write_reference_analysis_files(project_dir, analysis, markdown)
    return markdown
