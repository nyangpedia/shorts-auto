"""Reference artifacts inside a project folder (names are the stored project format)."""
from __future__ import annotations

import json
from pathlib import Path

from app.core.storage import remove_files, write_json_atomic, write_many_atomic, write_text_atomic
from app.references.models import ReferenceCandidate, ReferenceState
from app.scripts.files import clear_script_outputs

CANDIDATES_FILE = "reference_candidates.json"
SELECTED_REFERENCE_FILE = "selected_reference.json"
REFERENCE_SCRIPT_FILE = "reference_script.md"
REFERENCE_RAW_STT_FILE = "reference_raw_stt.json"
REFERENCE_ANALYSIS_FILE = "reference_analysis.json"
REFERENCE_ANALYSIS_MARKDOWN_FILE = "reference_analysis.md"
REFERENCE_AUDIO_FILE = "reference_audio.wav"
REFERENCE_AUDIO_PREFIX = "reference_audio"

# What becomes stale when an earlier stage is redone.
ANALYSIS_REFERENCE_FILES = [REFERENCE_ANALYSIS_FILE, REFERENCE_ANALYSIS_MARKDOWN_FILE]
DERIVED_REFERENCE_FILES = [REFERENCE_RAW_STT_FILE, REFERENCE_SCRIPT_FILE, *ANALYSIS_REFERENCE_FILES]
DOWNSTREAM_REFERENCE_FILES = [REFERENCE_AUDIO_FILE, *DERIVED_REFERENCE_FILES]


def write_reference_candidates(project_dir: Path, candidates: list[ReferenceCandidate]) -> None:
    write_json_atomic(project_dir / CANDIDATES_FILE, [c.model_dump() for c in candidates])


def read_reference_candidates(project_dir: Path) -> list[ReferenceCandidate]:
    path = project_dir / CANDIDATES_FILE
    if not path.exists():
        return []
    return [ReferenceCandidate.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]


def write_selected_reference(project_dir: Path, candidate: ReferenceCandidate) -> None:
    write_json_atomic(project_dir / SELECTED_REFERENCE_FILE, candidate.model_dump())


def read_selected_reference(project_dir: Path) -> ReferenceCandidate | None:
    path = project_dir / SELECTED_REFERENCE_FILE
    return ReferenceCandidate.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else None


def write_reference_script(project_dir: Path, script: str) -> None:
    write_text_atomic(project_dir / REFERENCE_SCRIPT_FILE, script)


def read_reference_script(project_dir: Path) -> str | None:
    path = project_dir / REFERENCE_SCRIPT_FILE
    return path.read_text(encoding="utf-8") if path.exists() else None


def write_reference_raw_stt(project_dir: Path, raw_stt: dict) -> None:
    write_json_atomic(project_dir / REFERENCE_RAW_STT_FILE, raw_stt)


def write_reference_analysis_files(project_dir: Path, analysis: dict, markdown: str) -> None:
    write_many_atomic({
        project_dir / REFERENCE_ANALYSIS_FILE: json.dumps(analysis, ensure_ascii=False, indent=2),
        project_dir / REFERENCE_ANALYSIS_MARKDOWN_FILE: markdown,
    })


def clear_reference_audio_files(project_dir: Path, keep_name: str) -> None:
    for path in project_dir.glob(f"{REFERENCE_AUDIO_PREFIX}.*"):
        if path.is_file() and path.name != keep_name:
            path.unlink()


def clear_downstream_reference_outputs(project_dir: Path) -> None:
    """A different reference was picked: everything made from the old one goes."""
    clear_reference_audio_files(project_dir, keep_name="")
    remove_files(project_dir, DOWNSTREAM_REFERENCE_FILES)
    clear_script_outputs(project_dir)


def clear_derived_reference_outputs(project_dir: Path) -> None:
    """New audio: its transcript, analysis and scripts go."""
    remove_files(project_dir, DERIVED_REFERENCE_FILES)
    clear_script_outputs(project_dir)


def clear_reference_analysis_outputs(project_dir: Path) -> None:
    remove_files(project_dir, ANALYSIS_REFERENCE_FILES)
    clear_script_outputs(project_dir)


def read_reference_state(project_dir: Path) -> ReferenceState:
    analysis_path = project_dir / REFERENCE_ANALYSIS_FILE
    report_path = project_dir / REFERENCE_ANALYSIS_MARKDOWN_FILE
    return ReferenceState(
        candidates=read_reference_candidates(project_dir),
        selected_reference=read_selected_reference(project_dir),
        reference_script=read_reference_script(project_dir),
        analysis=json.loads(analysis_path.read_text(encoding="utf-8")) if analysis_path.exists() else None,
        analysis_markdown=report_path.read_text(encoding="utf-8") if report_path.exists() else None,
    )
