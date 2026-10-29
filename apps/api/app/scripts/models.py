"""Script step data: the AI's drafts, the confirmed narration, and checks on it.
Field names are the stored format (candidates.json, final_script_state.json, fact_check.json)."""
from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

# draft_a / draft_b today; the other two only appear in projects from older versions
CandidateKind = Literal["draft_a", "draft_b", "same_topic", "different_topic"]
FINAL_SCRIPT_MAX_LENGTH = 5000
ISSUE_MAX_LENGTH = 300


def clean_text(value: str, field_name: str, max_length: int = 4000) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    if len(text) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters")
    return text


def _required(limit: int):
    return AfterValidator(lambda v: clean_text(v, "value", limit))


Required = Annotated[str, _required(4000)]


class ScriptCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    candidate_id: Annotated[str, Field(max_length=80), _required(4000)]
    candidate_type: CandidateKind
    title: Annotated[str, Field(max_length=200), _required(4000)]
    title_options: list[str] = Field(default_factory=list)
    description: str = Field(default="", max_length=1500)
    tags: str = Field(default="", max_length=1000)
    keywords: str = Field(default="", max_length=1000)
    hook: Annotated[str, Field(max_length=500), _required(4000)]
    target_viewer: Annotated[str, Field(max_length=500), _required(4000)]
    why_it_can_work: Annotated[str, Field(max_length=1200), _required(4000)]
    main_curiosity_question: Annotated[str, Field(max_length=500), _required(4000)]
    structure_summary: Annotated[str, Field(max_length=1200), _required(4000)]
    draft_script: Annotated[str, Field(max_length=5000), _required(4000)]
    borrowed_reference_structure: Annotated[str, Field(max_length=1600), _required(4000)]

    @field_validator("description")
    @classmethod
    def _plain_description(cls, value: str) -> str:
        """YouTube descriptions are plain text: drop markdown bold and quote marks the model likes to add."""
        return value.replace("**", "").replace('"', "").replace("'", "").strip()


class TtsValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_valid: bool
    issues: list[Annotated[str, _required(ISSUE_MAX_LENGTH)]] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _issues_match_verdict(self) -> "TtsValidationResult":
        if self.is_valid == bool(self.issues):
            raise ValueError("valid TTS results must not include issues" if self.is_valid
                             else "invalid TTS results must include at least one issue")
        return self


class FinalScriptState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_candidate_id: Annotated[str, _required(80)]
    feedback: str = ""
    final_script: Annotated[str, _required(FINAL_SCRIPT_MAX_LENGTH)]
    tts_validation: TtsValidationResult


FactVerdict = Literal["확실", "논란", "의심"]


class FactCheckClaim(BaseModel):
    model_config = ConfigDict(extra="ignore")

    quote: str = Field(max_length=300)
    verdict: FactVerdict
    reason: str = Field(max_length=500)
    search_query: str = Field(default="", max_length=200)


class FactCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    script_hash: str  # the check only applies to the exact script text it was made for
    claims: list[FactCheckClaim] = Field(default_factory=list)


class SimilarSentence(BaseModel):
    text: str
    score: float


class SimilarityResult(BaseModel):
    score: float
    level: Literal["낮음", "주의", "높음", "비교 불가"]
    comparable: bool
    sentences: list[SimilarSentence] = Field(default_factory=list)


class ScriptsState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[ScriptCandidate] = Field(default_factory=list)
    selected_candidate: Optional[ScriptCandidate] = None
    final_script: Optional[str] = None
    feedback: str = ""
    tts_validation: Optional[TtsValidationResult] = None
    fact_check: Optional[FactCheckResult] = None
    similarity: Optional[SimilarityResult] = None


# ── request bodies ──

class _Feedback(BaseModel):
    feedback: str = Field(default="", max_length=2000)

    @field_validator("feedback")
    @classmethod
    def _trim(cls, value: str) -> str:
        return value.strip()


class GenerateCandidatesRequest(_Feedback):
    model_config = ConfigDict(extra="ignore")


class FinalizeScriptRequest(_Feedback):
    model_config = ConfigDict(extra="forbid")


class SelectScriptCandidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: Annotated[str, Field(min_length=1, max_length=80), _required(80)]


class UpdateFinalScriptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    final_script: str = Field(min_length=1, max_length=FINAL_SCRIPT_MAX_LENGTH)
