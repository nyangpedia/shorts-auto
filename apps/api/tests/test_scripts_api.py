"""Script step over HTTP: drafts → pick → finalize."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app

ANALYSIS = {"primary_structure": "상식 반박", "supporting_structures": [], "hook_analysis": "훅", "curiosity_gap": "궁금증",
            "retention_analysis": "유지", "payoff_analysis": "보상", "risk_notes": [], "reusable_structure_notes": "구조",
            "section_breakdown": []}


def draft(candidate_id: str, title: str, script: str) -> dict:
    return {"candidate_id": candidate_id, "candidate_type": candidate_id, "title": title, "hook": script.split(".")[0],
            "target_viewer": "직장인", "why_it_can_work": "예상과 다른 원인", "main_curiosity_question": "왜?",
            "structure_summary": "오해, 원인, 반전, 해결.", "draft_script": script, "borrowed_reference_structure": "원인 이동 구조"}


class Writer:
    """Drafts for the draft prompt, a final script for anything else."""

    def __init__(self, api_key, model):
        pass

    def analyze(self, prompt: str):
        if "exactly two" in prompt:
            return {"candidates": [draft("draft_a", "돈이 안 모이는 이유", "돈을 못 모으는 건 의지 문제가 아닙니다. 기준이 틀렸습니다."),
                                   draft("draft_b", "잠을 망치는 습관", "잠을 못 자는 건 밤 문제가 아닙니다. 아침 첫 행동이 밤을 정합니다.")]}
        return {"final_script": "잠을 못 자는 이유는 밤이 아니라 아침에 있습니다. 첫 행동을 바꾸면 밤이 달라집니다."}


class DownWriter(Writer):
    def analyze(self, prompt: str):
        raise RuntimeError("openai unavailable")


def setup(tmp_path: Path, writer=Writer, with_reference: bool = True):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "local.settings.json").write_text('{"openai_api_key":"key"}', encoding="utf-8")
    client = TestClient(create_app(repo_root=tmp_path, analysis_client_factory=writer))
    pid = client.post("/api/projects", json={"project_title": "대본"}).json()["project"]["project_id"]
    folder = tmp_path / "outputs" / pid
    if with_reference:
        (folder / "reference_script.md").write_text("레퍼런스 대본", encoding="utf-8")
        (folder / "reference_analysis.json").write_text(json.dumps(ANALYSIS, ensure_ascii=False), encoding="utf-8")
    return client, f"/api/projects/{pid}", folder


def step(project: dict, name: str) -> str:
    return next(s["state"] for s in project["step_statuses"] if s["name"] == name)


def test_nothing_yet(tmp_path: Path):
    client, base, _ = setup(tmp_path, with_reference=False)
    state = client.get(f"{base}/scripts").json()
    assert (state["candidates"], state["selected_candidate"], state["final_script"]) == ([], None, None)


def test_drafts_pick_finalize(tmp_path: Path):
    client, base, folder = setup(tmp_path)

    assert len(client.post(f"{base}/scripts/candidates").json()["candidates"]) == 2
    picked = client.post(f"{base}/scripts/select", json={"candidate_id": "draft_b"})
    assert picked.json()["selected_candidate"]["candidate_id"] == "draft_b"
    final = client.post(f"{base}/scripts/finalize", json={"feedback": "더 짧고 강하게"}).json()["final_script"]
    assert "아침" in final
    assert client.get(f"{base}/scripts").json()["final_script"] == final

    for name in ["candidates.json", "selected_script_candidate.json", "final_script.md"]:
        assert (folder / name).exists(), name
    project = client.get(base).json()["project"]
    assert project["generated_files"]["script_candidates"] == "candidates.json"
    assert project["generated_files"]["final_script"] == "final_script.md"
    assert project["current_step"] == "Production"
    assert step(project, "Candidates") == step(project, "Script") == "succeeded"


def test_drafts_need_the_analysis(tmp_path: Path):
    client, base, _ = setup(tmp_path, with_reference=False)
    response = client.post(f"{base}/scripts/candidates")
    assert (response.status_code, response.json()["detail"]) == (400, "Reference script and analysis are required")


def test_finalize_needs_a_pick(tmp_path: Path):
    client, base, _ = setup(tmp_path)
    response = client.post(f"{base}/scripts/finalize", json={"feedback": ""})
    assert (response.status_code, response.json()["detail"]) == (400, "Select a script candidate before finalizing")


def test_model_error_fails_the_job(tmp_path: Path):
    client, base, _ = setup(tmp_path, writer=DownWriter)
    response = client.post(f"{base}/scripts/candidates")
    assert response.status_code == 400 and "openai unavailable" in response.json()["detail"]
    assert client.get(base).json()["project"]["job_history"][-1]["state"] == "failed"
