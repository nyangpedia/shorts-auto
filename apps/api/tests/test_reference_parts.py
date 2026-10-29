"""Reference step pieces without HTTP: audio download, transcript files, analysis parsing, saved state."""
from pathlib import Path

import pytest

from app.references.analysis import build_analysis_prompt, render_analysis_markdown, validate_reference_analysis, write_reference_analysis
from app.references.audio import AudioExtractionError, extract_reference_audio, validate_audio_upload_name
from app.references.files import REFERENCE_RAW_STT_FILE, REFERENCE_SCRIPT_FILE, read_reference_state, write_reference_candidates, write_reference_script, write_selected_reference
from app.references.models import ReferenceCandidate
from app.references.openai_clients import write_reference_stt_outputs

URL = "https://www.youtube.com/watch?v=abc123DEF45"
ANALYSIS = {
    "primary_structure": "common-sense conflict", "supporting_structures": ["question"],
    "hook_analysis": "첫 문장이 상식을 흔듭니다.", "curiosity_gap": "왜 그런지 궁금하게 만듭니다.",
    "retention_analysis": "중간에 반전을 넣습니다.", "payoff_analysis": "끝에서 답을 줍니다.",
    "risk_notes": ["근거가 약하면 과장처럼 보입니다."], "reusable_structure_notes": "상식 제시, 의문, 반전, 결론 순서.",
    "section_breakdown": [{"section": "Hook", "script_excerpt": "이걸 모르면 손해입니다.", "viewer_reaction": "멈춥니다.", "purpose": "궁금증"}],
}


# ── audio ──

@pytest.mark.parametrize("name,saved", [("voice.wav", "reference_audio.wav"), ("voice.mp3", "reference_audio.mp3"), ("voice.M4A", "reference_audio.m4a")])
def test_upload_names(name, saved):
    assert validate_audio_upload_name(name) == saved


@pytest.mark.parametrize("name", ["notes.txt", "voice"])
def test_upload_names_rejected(name):
    with pytest.raises(ValueError, match="Audio upload must be"):
        validate_audio_upload_name(name)


def test_download_runs_yt_dlp(tmp_path: Path):
    commands = []

    def runner(command):
        commands.append(command)
        (tmp_path / "reference_audio.wav").write_bytes(b"audio")
        return 0, "", ""

    assert extract_reference_audio(project_dir=tmp_path, url=URL, yt_dlp_binary="yt-dlp", runner=runner) == tmp_path / "reference_audio.wav"
    [command] = commands
    assert command[0] == "yt-dlp" and "--extract-audio" in command and "--audio-format" in command
    assert str(tmp_path / "reference_audio.%(ext)s") in command


@pytest.mark.parametrize("runner,message", [
    (lambda c: (1, "", "ffmpeg not found"), "ffmpeg not found"),
    (lambda c: (0, "ok", ""), "was not created"),
])
def test_download_failures_say_why(tmp_path: Path, runner, message):
    with pytest.raises(AudioExtractionError, match=message):
        extract_reference_audio(project_dir=tmp_path, url=URL, yt_dlp_binary="yt-dlp", runner=runner)


def test_missing_yt_dlp(tmp_path: Path):
    def runner(command):
        raise FileNotFoundError("missing binary")

    with pytest.raises(AudioExtractionError, match="yt-dlp binary not found"):
        extract_reference_audio(project_dir=tmp_path, url=URL, yt_dlp_binary="/missing/yt-dlp", runner=runner)


# ── transcript ──

@pytest.mark.parametrize("raw", [
    {"text": "첫 문장입니다.", "segments": [{"start": 0, "end": 1, "text": "첫 문장입니다."}]},
    {"text": "  첫 문장입니다.  "},
])
def test_transcript_files(tmp_path: Path, raw):
    assert write_reference_stt_outputs(tmp_path, raw) == "첫 문장입니다."
    assert (tmp_path / REFERENCE_RAW_STT_FILE).exists()
    assert (tmp_path / REFERENCE_SCRIPT_FILE).read_text(encoding="utf-8") == "첫 문장입니다.\n"


def test_saved_reference_state_reads_back(tmp_path: Path):
    video = ReferenceCandidate(video_id="abc123DEF45", url=URL, title="테스트 쇼츠", channel_id="channel-1", channel_name="채널",
                               thumbnail_url="https://img.youtube.com/vi/abc123DEF45/default.jpg", upload_date="2026-10-01T00:00:00Z",
                               duration_seconds=45, view_count=120000, subscriber_count=3000, source_type="search")
    write_reference_candidates(tmp_path, [video])
    write_selected_reference(tmp_path, video)
    write_reference_script(tmp_path, "첫 문장입니다.")

    state = read_reference_state(tmp_path)
    assert state.candidates[0].video_id == "abc123DEF45"
    assert state.selected_reference.title == "테스트 쇼츠"
    assert state.reference_script == "첫 문장입니다."


# ── analysis ──

def test_analysis_prompt_asks_why_it_works():
    prompt = build_analysis_prompt("이걸 모르면 손해입니다.")
    for needle in ["why viewers stop", "keep watching", "feel payoff", "section_breakdown", "이걸 모르면 손해입니다."]:
        assert needle in prompt, needle


def test_analysis_report(tmp_path: Path):
    markdown = render_analysis_markdown(ANALYSIS)
    for needle in ["# Reference Analysis", "common-sense conflict", "첫 문장이 상식을 흔듭니다.", "근거가 약하면 과장처럼 보입니다."]:
        assert needle in markdown, needle
    assert "# Reference Analysis" in write_reference_analysis(tmp_path, ANALYSIS)
    assert (tmp_path / "reference_analysis.json").exists() and (tmp_path / "reference_analysis.md").exists()


@pytest.mark.parametrize("bad", [
    {"primary_structure": "missing fields"},
    {**ANALYSIS, "supporting_structures": 12345},
    {**ANALYSIS, "section_breakdown": [{"section": "Hook"}]},
])
def test_malformed_analysis(bad):
    with pytest.raises(ValueError):
        validate_reference_analysis(bad)


def test_single_strings_become_lists():
    fixed = validate_reference_analysis({**ANALYSIS, "risk_notes": "하나의 위험", "supporting_structures": "단일 구조"})
    assert (fixed["risk_notes"], fixed["supporting_structures"]) == (["하나의 위험"], ["단일 구조"])
