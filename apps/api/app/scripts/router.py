"""Script step API: two drafts from the analysis, pick one, polish it for TTS, edit it, fact-check it."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from app.core.settings import AppSettings
from app.projects.progress import job, update_progress
from app.projects.service import read_project, save_project
from app.references.files import REFERENCE_ANALYSIS_FILE, REFERENCE_SCRIPT_FILE
from app.references.openai_clients import AnalysisClient
from app.scripts.files import (
    FACT_CHECK_FILE,
    FINAL_SCRIPT_FILE,
    FINAL_SCRIPT_STATE_FILE,
    SCRIPT_CANDIDATES_FILE,
    SELECTED_SCRIPT_CANDIDATE_FILE,
    read_final_script_state,
    read_script_candidates,
    read_script_state,
    write_fact_check,
    write_final_script_state,
    write_script_candidates,
    write_selected_script_candidate,
)
from app.scripts.generation import (
    build_candidate_generation_prompt,
    build_fact_check_prompt,
    build_final_script_prompt,
    build_final_script_state,
    extract_final_script,
    parse_fact_check,
    validate_candidate_payload,
)
from app.scripts.models import FinalizeScriptRequest, GenerateCandidatesRequest, SelectScriptCandidateRequest, UpdateFinalScriptRequest


def create_scripts_router(
    outputs_dir_provider: Callable[[], Path],
    settings_provider: Callable[[], AppSettings],
    script_client_factory: Callable[[str, str], AnalysisClient],
) -> APIRouter:
    router = APIRouter(prefix="/api/projects/{project_id}/scripts", tags=["scripts"])
    Outputs = Depends(outputs_dir_provider)
    Settings = Depends(settings_provider)

    def folder(outputs: Path, project_id: str) -> Path:
        try:
            read_project(outputs, project_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return outputs / project_id

    def llm(settings: AppSettings) -> AnalysisClient:
        return script_client_factory(settings.llm_api_key, settings.openai_analysis_model)

    def confirmed(path: Path):
        current = read_final_script_state(path)
        if current is None:
            raise HTTPException(status_code=400, detail="먼저 대본을 확정해주세요.")
        return current

    @router.get("")
    def get_scripts(project_id: str, outputs: Path = Outputs):
        return read_script_state(folder(outputs, project_id)).model_dump()

    @router.post("/candidates")
    def generate_candidates(project_id: str, payload: GenerateCandidatesRequest | None = None,
                            outputs: Path = Outputs, settings: AppSettings = Settings):
        path = folder(outputs, project_id)
        if not (path / REFERENCE_SCRIPT_FILE).exists() or not (path / REFERENCE_ANALYSIS_FILE).exists():
            raise HTTPException(status_code=400, detail="Reference script and analysis are required")
        try:
            with job(outputs, project_id, "script_candidates", "Generate script candidates",
                     "Generating script drafts based on analysis and feedback", provider="llm",
                     command=settings.openai_analysis_model, inputs=[REFERENCE_SCRIPT_FILE, REFERENCE_ANALYSIS_FILE]) as run:
                prompt = build_candidate_generation_prompt(
                    (path / REFERENCE_SCRIPT_FILE).read_text(encoding="utf-8"),
                    json.loads((path / REFERENCE_ANALYSIS_FILE).read_text(encoding="utf-8")),
                    payload.feedback if payload else "",
                )
                drafts = validate_candidate_payload(llm(settings).analyze(prompt))
                write_script_candidates(path, drafts)
                update_progress(
                    outputs, project_id, current="Candidates",
                    steps={"Candidates": ("succeeded", f"{len(drafts)} candidate drafts are ready for selection."),
                           "Script": ("waiting", "Candidate drafts generated. Select a candidate to finalize script.")},
                    files={"script_candidates": SCRIPT_CANDIDATES_FILE},
                )
                run.succeed("Script candidates generated", [SCRIPT_CANDIDATES_FILE])
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc) or type(exc).__name__) from exc
        return {"candidates": [d.model_dump() for d in drafts]}

    @router.post("/select")
    def select_candidate(project_id: str, payload: SelectScriptCandidateRequest, outputs: Path = Outputs):
        path = folder(outputs, project_id)
        chosen = next((c for c in read_script_candidates(path) if c.candidate_id == payload.candidate_id), None)
        if chosen is None:
            raise HTTPException(status_code=404, detail="Script candidate not found")
        write_selected_script_candidate(path, chosen)
        project = read_project(outputs, project_id)
        project.selected_candidate_id = chosen.candidate_id
        save_project(outputs, project)
        update_progress(
            outputs, project_id, current="Script",
            steps={"Candidates": ("succeeded", "Script candidate selected."), "Script": ("running", "Ready to finalize TTS script.")},
            files={"selected_script_candidate": SELECTED_SCRIPT_CANDIDATE_FILE},
        )
        return {"selected_candidate": chosen.model_dump()}

    @router.post("/finalize")
    def finalize_script(project_id: str, payload: FinalizeScriptRequest, outputs: Path = Outputs, settings: AppSettings = Settings):
        path = folder(outputs, project_id)
        chosen = read_script_state(path).selected_candidate
        if chosen is None:
            raise HTTPException(status_code=400, detail="Select a script candidate before finalizing")
        try:
            with job(outputs, project_id, "final_script", "Finalize TTS script", "Finalizing TTS-ready script",
                     provider="llm", command=settings.openai_analysis_model, inputs=[SELECTED_SCRIPT_CANDIDATE_FILE]) as run:
                script = extract_final_script(llm(settings).analyze(build_final_script_prompt(chosen, payload.feedback)))
                state = build_final_script_state(chosen.candidate_id, payload.feedback, script)
                write_final_script_state(path, state)
                # Scenes are planned later, in the voice/style step, with the style the user picks and the
                # real narration timing.
                update_progress(
                    outputs, project_id, current="Production",
                    steps={"Script": ("succeeded", "Final TTS-ready script complete."),
                           "Production": ("waiting", "Script and scene prompts ready. Ready for TTS voice and images.")},
                    files={"final_script": FINAL_SCRIPT_FILE, "final_script_state": FINAL_SCRIPT_STATE_FILE},
                )
                run.succeed("Final script complete", [FINAL_SCRIPT_FILE, FINAL_SCRIPT_STATE_FILE])
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc) or type(exc).__name__) from exc
        return state.model_dump()

    @router.put("/final")
    def update_final_script(project_id: str, payload: UpdateFinalScriptRequest, outputs: Path = Outputs):
        path = folder(outputs, project_id)
        current = confirmed(path)
        if current.final_script.strip() == payload.final_script.strip():
            return read_script_state(path).model_dump()
        try:
            write_final_script_state(path, build_final_script_state(current.selected_candidate_id, current.feedback, payload.final_script))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        project = read_project(outputs, project_id)
        for step in project.step_statuses:
            if step.name == "Script":
                step.message = "대본을 직접 수정했습니다."
            elif step.name == "Production" and step.state == "succeeded":
                step.state, step.message = "waiting", "대본이 바뀌었습니다. 음성과 씬을 다시 만들어주세요."
        save_project(outputs, project)
        return read_script_state(path).model_dump()

    @router.post("/factcheck")
    def fact_check_script(project_id: str, outputs: Path = Outputs, settings: AppSettings = Settings):
        path = folder(outputs, project_id)
        script = confirmed(path).final_script
        try:
            write_fact_check(path, parse_fact_check(llm(settings).analyze(build_fact_check_prompt(script)), script))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc) or type(exc).__name__) from exc
        update_progress(outputs, project_id, files={"fact_check": FACT_CHECK_FILE})
        return read_script_state(path).model_dump()

    return router
