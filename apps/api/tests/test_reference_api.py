"""Reference step over HTTP: search → pick → audio → transcript → analysis, and what each step clears."""
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.references.models import ReferenceCandidate
from app.references.youtube import YouTubeClient

ANALYSIS = {
    "primary_structure": "common-sense conflict",
    "supporting_structures": ["question"],
    "hook_analysis": "첫 문장이 상식을 흔듭니다.",
    "curiosity_gap": "왜 그런지 궁금하게 만듭니다.",
    "retention_analysis": "중간에 반전을 넣습니다.",
    "payoff_analysis": "끝에서 답을 줍니다.",
    "risk_notes": ["근거가 약하면 과장처럼 보입니다."],
    "reusable_structure_notes": "상식 제시, 의문, 반전, 결론 순서.",
    "section_breakdown": [{"section": "Hook", "script_excerpt": "이걸 모르면 손해입니다.", "viewer_reaction": "멈춥니다.", "purpose": "궁금증"}],
}


def video(video_id: str, subscribers: int, views: int = 100000, kind: str = "search") -> ReferenceCandidate:
    return ReferenceCandidate(
        video_id=video_id, url=f"https://www.youtube.com/watch?v={video_id}", title=video_id,
        channel_id=f"ch-{video_id}", channel_name="채널", thumbnail_url="https://example.com/t.jpg",
        upload_date="2026-10-01T00:00:00Z", duration_seconds=44, view_count=views,
        subscriber_count=subscribers, source_type=kind,
    )


class YouTube:
    def __init__(self, api_key: str):
        pass

    def search(self, request):
        return [video("highratio1", 1000), video("lowratio1", 10000)]

    def get_direct(self, url: str):
        return video("direct1", 5000, views=200000, kind="direct")


class DownYouTube(YouTube):
    def search(self, request):
        raise httpx.ConnectError("network down")


def transcriber(result=None, error: str | None = None):
    class Client:
        def __init__(self, api_key, model):
            pass

        def transcribe(self, audio_path):
            if error:
                raise RuntimeError(error)
            return result or {"text": "첫 문장입니다. 이 영상은 아주 짧지 않습니다.", "segments": [{"start": 0, "end": 1, "text": "첫 문장입니다. 이 영상은 아주 짧지 않습니다."}]}
    return Client


def analyzer(payload: dict | None = None, error: str | None = None):
    class Client:
        def __init__(self, api_key, model):
            pass

        def analyze(self, prompt):
            if error:
                raise RuntimeError(error)
            return payload if payload is not None else ANALYSIS
    return Client


def extracted(project_dir: Path, url: str, yt_dlp_binary: str) -> Path:
    out = project_dir / "reference_audio.wav"
    out.write_bytes(b"extracted audio")
    return out


class Setup:
    def __init__(self, tmp_path: Path, settings: dict | None = None, **factories):
        if settings:
            (tmp_path / "config").mkdir()
            (tmp_path / "config" / "local.settings.json").write_text(json.dumps(settings), encoding="utf-8")
        factories.setdefault("youtube_client_factory", YouTube)
        self.client = TestClient(create_app(repo_root=tmp_path, **factories))
        self.pid = self.client.post("/api/projects", json={"project_title": "레퍼런스"}).json()["project"]["project_id"]
        self.dir = tmp_path / "outputs" / self.pid

    def post(self, rest: str, **kwargs):
        return self.client.post(f"/api/projects/{self.pid}/reference{rest}", **kwargs)

    def state(self) -> dict:
        return self.client.get(f"/api/projects/{self.pid}/reference").json()

    def project(self) -> dict:
        return self.client.get(f"/api/projects/{self.pid}").json()["project"]

    def last_job(self) -> dict:
        return self.project()["job_history"][-1]

    def upload(self, name: str, data: bytes, mime: str):
        return self.post("/audio/upload", files={"file": (name, data, mime)})

    def seed(self, **files: str) -> None:
        for name, text in files.items():
            (self.dir / name.replace("__", ".")).write_text(text, encoding="utf-8")


def step(project: dict, name: str) -> tuple[str, str]:
    found = next(s for s in project["step_statuses"] if s["name"] == name)
    return found["state"], found["message"]


KEYED = {"youtube_api_key": "key", "openai_api_key": "key"}


# ── search and pick ──

def test_search_then_direct_then_pick(tmp_path: Path):
    s = Setup(tmp_path)
    assert step(s.project(), "Reference")[0] != "succeeded"

    found = s.post("/search", json={"keyword": "돈"})
    assert [c["video_id"] for c in found.json()["candidates"]] == ["highratio1", "lowratio1"]
    assert step(s.project(), "Reference")[0] != "succeeded"  # searching alone doesn't finish the step

    direct = s.post("/direct", json={"url": "https://www.youtube.com/watch?v=direct1"})
    assert [c["video_id"] for c in direct.json()["candidates"]] == ["highratio1", "direct1", "lowratio1"]  # by views/subs

    assert s.post("/select", json={"video_id": "direct1"}).status_code == 200
    assert s.state()["selected_reference"]["video_id"] == "direct1"
    project = s.project()
    assert project["selected_reference_path"] == project["generated_files"]["selected_reference"] == "selected_reference.json"
    assert project["current_step"] == "STT"
    assert step(project, "Reference")[0] == "succeeded"
    assert step(project, "STT") == ("waiting", "Reference selected. Ready for audio and STT.")


def test_search_without_youtube_key_fails_the_job(tmp_path: Path):
    s = Setup(tmp_path, youtube_client_factory=YouTubeClient)  # the real client checks the key
    response = s.post("/search", json={"keyword": "돈"})
    assert (response.status_code, response.json()["detail"]) == (400, "YouTube API key is missing")
    assert (s.last_job()["state"], s.last_job()["error_message"]) == ("failed", "YouTube API key is missing")


def test_search_network_error_fails_the_job(tmp_path: Path):
    s = Setup(tmp_path, {"youtube_api_key": "key"}, youtube_client_factory=DownYouTube)
    response = s.post("/search", json={"keyword": "돈"})
    assert response.status_code == 400 and "network down" in response.json()["detail"]
    assert s.last_job()["state"] == "failed" and "network down" in s.last_job()["error_message"]


def test_picking_again_clears_everything_after_it(tmp_path: Path):
    s = Setup(tmp_path)
    s.post("/search", json={"keyword": "돈"})
    s.post("/direct", json={"url": "https://www.youtube.com/watch?v=direct1"})
    (s.dir / "reference_audio.mp3").write_bytes(b"old audio")
    s.seed(reference_script__md="old", reference_analysis__json="{}", reference_analysis__md="old",
           candidates__json="[]", selected_script_candidate__json="{}", final_script__md="old", final_script_state__json="{}")

    assert s.post("/select", json={"video_id": "direct1"}).status_code == 200
    for gone in ["reference_audio.mp3", "candidates.json", "selected_script_candidate.json", "final_script.md", "final_script_state.json"]:
        assert not (s.dir / gone).exists(), gone
    state = s.state()
    assert state["reference_script"] is state["analysis"] is state["analysis_markdown"] is None
    assert "reference_script" not in s.project()["generated_files"]
    assert step(s.project(), "Analysis")[0] == "waiting"


# ── audio ──

def test_upload_saves_audio(tmp_path: Path):
    s = Setup(tmp_path)
    response = s.upload("reference.wav", b"audio", "audio/wav")
    assert response.json()["audio_path"] == "reference_audio.wav"
    assert (s.dir / "reference_audio.wav").read_bytes() == b"audio"
    assert s.project()["generated_files"]["reference_audio"] == "reference_audio.wav"


@pytest.mark.parametrize("name,data,mime,message", [
    ("reference.wav", b"", "audio/wav", "Audio upload must not be empty"),
    ("notes.txt", b"text", "text/plain", "Audio upload must be"),
])
def test_upload_rejects_bad_files(tmp_path: Path, name, data, mime, message):
    response = Setup(tmp_path).upload(name, data, mime)
    assert response.status_code == 400 and message in response.json()["detail"]


def test_new_upload_clears_transcript_and_analysis(tmp_path: Path):
    s = Setup(tmp_path)
    s.seed(reference_raw_stt__json="{}", reference_script__md="old", reference_analysis__json="{}", reference_analysis__md="old")
    assert s.upload("reference.wav", b"new audio", "audio/wav").status_code == 200
    assert not (s.dir / "reference_raw_stt.json").exists()
    state = s.state()
    assert state["reference_script"] is state["analysis"] is state["analysis_markdown"] is None


def test_upload_with_another_extension_replaces_the_old_file(tmp_path: Path):
    s = Setup(tmp_path)
    (s.dir / "reference_audio.wav").write_bytes(b"old audio")
    assert s.upload("reference.mp3", b"new audio", "audio/mpeg").json()["audio_path"] == "reference_audio.mp3"
    assert not (s.dir / "reference_audio.wav").exists()
    assert (s.dir / "reference_audio.mp3").read_bytes() == b"new audio"


def test_extract_needs_a_picked_video(tmp_path: Path):
    response = Setup(tmp_path).post("/audio/extract")
    assert (response.status_code, response.json()["detail"]) == (400, "Select a reference before extracting audio")


def test_extract_saves_audio_and_drops_old_transcript(tmp_path: Path):
    s = Setup(tmp_path, {"youtube_api_key": "key"}, audio_extractor=extracted)
    s.post("/search", json={"keyword": "돈"})
    s.post("/select", json={"video_id": "highratio1"})
    s.seed(reference_script__md="old script")

    assert s.post("/audio/extract").json()["audio_path"] == "reference_audio.wav"
    assert (s.dir / "reference_audio.wav").read_bytes() == b"extracted audio"
    project = s.project()
    assert project["generated_files"]["reference_audio"] == "reference_audio.wav"
    assert (project["job_history"][-1]["state"], project["job_history"][-1]["output_paths"]) == ("succeeded", ["reference_audio.wav"])
    assert s.state()["reference_script"] is None


def test_extract_without_yt_dlp_fails_the_job(tmp_path: Path):
    s = Setup(tmp_path, {"youtube_api_key": "key", "yt_dlp_binary": "/missing/yt-dlp"})
    s.post("/search", json={"keyword": "돈"})
    s.post("/select", json={"video_id": "highratio1"})
    response = s.post("/audio/extract")
    assert response.status_code == 400 and "yt-dlp binary not found" in response.json()["detail"]
    assert s.last_job()["state"] == "failed" and "yt-dlp binary not found" in s.last_job()["error_message"]


# ── transcript ──

def test_transcribe_writes_script_and_moves_on(tmp_path: Path):
    s = Setup(tmp_path, KEYED, transcription_client_factory=transcriber())
    (s.dir / "reference_audio.wav").write_bytes(b"audio")
    s.seed(reference_analysis__json='{"old":true}', reference_analysis__md="old")

    assert s.post("/stt").json()["reference_script"] == "첫 문장입니다. 이 영상은 아주 짧지 않습니다."
    project = s.project()
    assert project["generated_files"]["reference_raw_stt"] == "reference_raw_stt.json"
    assert project["generated_files"]["reference_script"] == "reference_script.md"
    assert (s.dir / "reference_raw_stt.json").exists() and (s.dir / "reference_script.md").exists()
    assert project["current_step"] == "Analysis"
    assert step(project, "STT")[0] == "succeeded" and step(project, "Analysis")[0] == "waiting"
    assert project["job_history"][-1]["state"] == "succeeded"
    # the old analysis was for the old transcript
    assert s.state()["analysis"] is None and s.state()["analysis_markdown"] is None
    assert "reference_analysis" not in project["generated_files"]


def test_transcribe_reads_the_uploaded_extension(tmp_path: Path):
    s = Setup(tmp_path, KEYED, transcription_client_factory=transcriber())
    s.upload("reference.mp3", b"audio", "audio/mpeg")
    assert s.post("/stt").status_code == 200
    assert s.last_job()["input_paths"] == ["reference_audio.mp3"]


def test_transcribe_downloads_audio_first_when_missing(tmp_path: Path):
    s = Setup(tmp_path, KEYED, audio_extractor=extracted, transcription_client_factory=transcriber())
    s.post("/search", json={"keyword": "돈"})
    s.post("/select", json={"video_id": "highratio1"})

    assert s.post("/stt").status_code == 200
    project = s.project()
    assert (s.dir / "reference_audio.wav").read_bytes() == b"extracted audio"
    assert project["generated_files"]["reference_audio"] == "reference_audio.wav"
    assert [j["job_type"] for j in project["job_history"][-2:]] == ["reference_audio_extract", "reference_stt"]
    assert step(project, "STT")[0] == "succeeded"


def test_transcribe_without_audio(tmp_path: Path):
    response = Setup(tmp_path, KEYED, transcription_client_factory=transcriber()).post("/stt")
    assert (response.status_code, response.json()["detail"]) == (400, "Reference audio is missing")


def test_transcribe_does_not_pick_up_a_stray_file(tmp_path: Path):
    s = Setup(tmp_path, KEYED, transcription_client_factory=transcriber())
    s.upload("reference.mp3", b"audio", "audio/mpeg")
    (s.dir / "reference_audio.mp3").unlink()
    (s.dir / "reference_audio.wav").write_bytes(b"stale audio")  # not the file the project recorded

    response = s.post("/stt")
    assert (response.status_code, response.json()["detail"]) == (400, "Reference audio is missing")
    jobs = s.project()["job_history"]
    assert not jobs or jobs[-1]["job_type"] != "reference_stt"


def test_transcriber_error_fails_the_job(tmp_path: Path):
    s = Setup(tmp_path, KEYED, transcription_client_factory=transcriber(error="openai unavailable"))
    (s.dir / "reference_audio.wav").write_bytes(b"audio")
    response = s.post("/stt")
    assert response.status_code == 400 and "openai unavailable" in response.json()["detail"]
    project = s.project()
    assert project["job_history"][-1]["state"] == "failed" and "openai unavailable" in project["job_history"][-1]["error_message"]
    assert "reference_raw_stt" not in project["generated_files"]


# ── analysis ──

def test_analyze_writes_report_and_moves_on(tmp_path: Path):
    s = Setup(tmp_path, KEYED, analysis_client_factory=analyzer())
    s.seed(reference_script__md="이걸 모르면 손해입니다.")

    assert s.post("/analyze").json()["analysis"]["primary_structure"] == "common-sense conflict"
    assert "Reference Analysis" in s.state()["analysis_markdown"]
    project = s.project()
    assert project["generated_files"]["reference_analysis"] == "reference_analysis.json"
    assert project["generated_files"]["reference_analysis_markdown"] == "reference_analysis.md"
    assert (s.dir / "reference_analysis.json").exists() and (s.dir / "reference_analysis.md").exists()
    assert project["current_step"] == "Candidates"
    assert step(project, "Analysis")[0] == "succeeded" and step(project, "Candidates")[0] == "waiting"
    assert project["job_history"][-1]["state"] == "succeeded"


def test_analyze_without_transcript(tmp_path: Path):
    response = Setup(tmp_path, KEYED, analysis_client_factory=analyzer()).post("/analyze")
    assert (response.status_code, response.json()["detail"]) == (400, "Reference script is missing")


def test_analyzer_error_fails_the_job(tmp_path: Path):
    s = Setup(tmp_path, KEYED, analysis_client_factory=analyzer(error="analysis unavailable"))
    s.seed(reference_script__md="이걸 모르면 손해입니다.")
    response = s.post("/analyze")
    assert response.status_code == 400 and "analysis unavailable" in response.json()["detail"]
    project = s.project()
    assert project["job_history"][-1]["state"] == "failed" and "analysis unavailable" in project["job_history"][-1]["error_message"]
    assert "reference_analysis" not in project["generated_files"]


def test_failed_rerun_drops_the_previous_analysis(tmp_path: Path):
    good = Setup(tmp_path, KEYED, analysis_client_factory=analyzer())
    good.seed(reference_script__md="이걸 모르면 손해입니다.")
    assert good.post("/analyze").status_code == 200

    bad = TestClient(create_app(repo_root=tmp_path, youtube_client_factory=YouTube, analysis_client_factory=analyzer(error="down")))
    assert bad.post(f"/api/projects/{good.pid}/reference/analyze").status_code == 400
    state = good.state()
    assert state["analysis"] is None and state["analysis_markdown"] is None
    project = good.project()
    assert project["current_step"] == "Analysis" and step(project, "Analysis")[0] == "failed"
    assert "reference_analysis" not in project["generated_files"]


def test_analysis_missing_fields_is_rejected(tmp_path: Path):
    s = Setup(tmp_path, KEYED, analysis_client_factory=analyzer({"primary_structure": "missing fields"}))
    s.seed(reference_script__md="이걸 모르면 손해입니다.")
    response = s.post("/analyze")
    assert response.status_code == 400 and "Field required" in response.json()["detail"]
    assert s.last_job()["state"] == "failed"


def test_video_without_speech_is_analysed_by_its_title(tmp_path: Path):
    seen = []

    class Recorder:
        def __init__(self, api_key, model):
            pass

        def analyze(self, prompt):
            seen.append(prompt)
            return ANALYSIS

    s = Setup(tmp_path, KEYED, audio_extractor=extracted, transcription_client_factory=transcriber({"text": "", "segments": []}),
              analysis_client_factory=Recorder)
    s.post("/search", json={"keyword": "돈"})
    s.post("/select", json={"video_id": "highratio1"})

    script = s.post("/stt").json()["reference_script"]
    assert "내레이션 없는 영상" in script and "highratio1" in script  # the title stands in for the empty transcript
    assert step(s.project(), "STT") == ("succeeded", "말소리가 없는 영상이라 제목으로 분석합니다.")
    assert s.post("/analyze").status_code == 200
    assert "highratio1" in seen[0]


def test_empty_script_is_never_analysed(tmp_path: Path):
    s = Setup(tmp_path, KEYED, analysis_client_factory=analyzer())
    s.seed(reference_script__md="\n")
    response = s.post("/analyze")
    assert response.status_code == 400 and "비어 있습니다" in response.json()["detail"]
