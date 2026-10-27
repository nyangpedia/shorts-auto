from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from tests.test_scripts_api import FakeScriptClient, create_project, write_reference_inputs


class FactCheckingClient(FakeScriptClient):
    def analyze(self, prompt: str):
        if "판정 기준" in prompt:
            return {
                "claims": [
                    {"quote": "밤이 아니라 아침", "verdict": "확실", "reason": "수면 위생 연구와 일치", "search_query": "아침 햇빛 수면"},
                    {"quote": "첫 행동을 바꾸면", "verdict": "의심", "reason": "단정하기엔 근거 부족", "search_query": "아침 습관 수면 연구"},
                    {"quote": "깨진 항목", "verdict": "모름", "reason": "x"},
                ]
            }
        return super().analyze(prompt)


def finalized_client(tmp_path: Path) -> tuple[TestClient, str]:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "local.settings.json").write_text('{"openai_api_key":"key"}', encoding="utf-8")
    client = TestClient(create_app(repo_root=tmp_path, analysis_client_factory=FactCheckingClient))
    project_id = create_project(client)
    write_reference_inputs(tmp_path / "outputs" / project_id)
    base = f"/api/projects/{project_id}/scripts"
    client.post(f"{base}/candidates")
    client.post(f"{base}/select", json={"candidate_id": "different-topic-1"})
    assert client.post(f"{base}/finalize", json={"feedback": ""}).status_code == 200
    return client, base


def test_direct_edit_saves_script_and_invalidates_fact_check(tmp_path: Path):
    client, base = finalized_client(tmp_path)

    checked = client.post(f"{base}/factcheck").json()["fact_check"]
    assert [c["verdict"] for c in checked["claims"]] == ["의심", "확실"]  # invalid verdict dropped, doubts first

    edited = client.put(f"{base}/final", json={"final_script": "제가 직접 고친 대본입니다. 아침 햇빛이 중요합니다."})
    assert edited.status_code == 200
    assert edited.json()["final_script"].startswith("제가 직접 고친")
    assert edited.json()["fact_check"] is None  # check was for the old text
    assert "제가 직접 고친" in (tmp_path / "outputs" / base.split("/")[3] / "final_script.md").read_text(encoding="utf-8")


def test_direct_edit_requires_finalized_script(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path, analysis_client_factory=FactCheckingClient))
    project_id = create_project(client)

    response = client.put(f"/api/projects/{project_id}/scripts/final", json={"final_script": "대본"})

    assert response.status_code == 400
