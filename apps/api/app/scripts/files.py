"""Script step files in a project folder (names are the stored format)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.core.storage import remove_files, write_json_atomic, write_many_atomic
from app.scripts.models import FactCheckResult, FinalScriptState, ScriptCandidate, ScriptsState

SCRIPT_CANDIDATES_FILE = "candidates.json"
SELECTED_SCRIPT_CANDIDATE_FILE = "selected_script_candidate.json"
FINAL_SCRIPT_FILE = "final_script.md"
FINAL_SCRIPT_STATE_FILE = "final_script_state.json"
FACT_CHECK_FILE = "fact_check.json"
SCRIPT_OUTPUT_FILES = [SCRIPT_CANDIDATES_FILE, SELECTED_SCRIPT_CANDIDATE_FILE, FINAL_SCRIPT_FILE, FINAL_SCRIPT_STATE_FILE, FACT_CHECK_FILE]


def script_hash(script: str) -> str:
    return hashlib.sha1(script.strip().encode("utf-8")).hexdigest()


def write_script_candidates(project_dir: Path, candidates: list[ScriptCandidate]) -> None:
    write_json_atomic(project_dir / SCRIPT_CANDIDATES_FILE, [c.model_dump() for c in candidates])


def read_script_candidates(project_dir: Path) -> list[ScriptCandidate]:
    path = project_dir / SCRIPT_CANDIDATES_FILE
    if not path.exists():
        return []
    return [ScriptCandidate.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]


def write_selected_script_candidate(project_dir: Path, candidate: ScriptCandidate) -> None:
    write_json_atomic(project_dir / SELECTED_SCRIPT_CANDIDATE_FILE, candidate.model_dump())


def read_selected_script_candidate(project_dir: Path) -> ScriptCandidate | None:
    path = project_dir / SELECTED_SCRIPT_CANDIDATE_FILE
    return ScriptCandidate.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else None


def write_final_script_state(project_dir: Path, state: FinalScriptState) -> None:
    """The JSON state is what the app reads; final_script.md is the readable export (and the TTS input).
    Both are swapped in together so a crash can't leave a new script without its validation."""
    write_many_atomic({
        project_dir / FINAL_SCRIPT_FILE: state.final_script.strip() + "\n",
        project_dir / FINAL_SCRIPT_STATE_FILE: json.dumps(state.model_dump(), ensure_ascii=False, indent=2),
    })


def read_final_script_state(project_dir: Path) -> FinalScriptState | None:
    path = project_dir / FINAL_SCRIPT_STATE_FILE
    return FinalScriptState.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else None


def write_fact_check(project_dir: Path, result: FactCheckResult) -> None:
    write_json_atomic(project_dir / FACT_CHECK_FILE, result.model_dump())


def read_fact_check(project_dir: Path, current_script: str | None) -> FactCheckResult | None:
    """The saved check, only if it was made for the script as it reads now."""
    path = project_dir / FACT_CHECK_FILE
    if not current_script or not path.exists():
        return None
    result = FactCheckResult.model_validate_json(path.read_text(encoding="utf-8"))
    return result if result.script_hash == script_hash(current_script) else None


def _similarity(project_dir: Path, final_script: str | None):
    from app.references.files import REFERENCE_SCRIPT_FILE  # local import: references.files imports this module
    from app.scripts.similarity import check_similarity

    reference = project_dir / REFERENCE_SCRIPT_FILE
    if not final_script or not reference.exists():
        return None
    return check_similarity(final_script, reference.read_text(encoding="utf-8"))


def read_script_state(project_dir: Path) -> ScriptsState:
    final = read_final_script_state(project_dir)
    script = final.final_script if final else None
    return ScriptsState(
        candidates=read_script_candidates(project_dir),
        selected_candidate=read_selected_script_candidate(project_dir),
        final_script=script,
        feedback=final.feedback if final else "",
        tts_validation=final.tts_validation if final else None,
        fact_check=read_fact_check(project_dir, script),
        similarity=_similarity(project_dir, script),
    )


def clear_script_outputs(project_dir: Path) -> None:
    remove_files(project_dir, SCRIPT_OUTPUT_FILES)
