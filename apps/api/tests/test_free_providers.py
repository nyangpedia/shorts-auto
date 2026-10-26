from pathlib import Path
from types import SimpleNamespace

from app.references.openai_clients import FasterWhisperClient


class FakeModel:
    def transcribe(self, path, language):
        segs = (SimpleNamespace(start=i, end=i + 1, text=f" 문장{i}") for i in range(2))
        return segs, SimpleNamespace(duration=2.0)


def test_segments_survive_generator():
    client = FasterWhisperClient.__new__(FasterWhisperClient)
    client.whisper_model = FakeModel()
    out = client.transcribe(Path("x.wav"))
    assert [s["text"] for s in out["segments"]] == [" 문장0", " 문장1"]
    assert out["text"] == "문장0 문장1"


def test_analysis_strips_code_fence_for_compatible_providers():
    from app.references.openai_clients import OpenAIAnalysisClient

    client = OpenAIAnalysisClient("k", "gemini-2.5-flash", "https://example.invalid/")
    msg = SimpleNamespace(content='```json\n{"ok": 1}\n```')
    client.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kw: SimpleNamespace(choices=[SimpleNamespace(message=msg)]) if "response_format" not in kw else None
    )))
    assert client.analyze("p") == {"ok": 1}



def test_gemini_tts_writes_sped_up_wav(tmp_path, monkeypatch):
    import base64
    import google.genai as genai
    from app.core.settings import AppSettings
    from app.production import service

    calls = {}

    class FakeClient:
        def __init__(self, api_key):
            self.interactions = SimpleNamespace(create=self.create)

        def create(self, **kw):
            calls.update(kw)
            return SimpleNamespace(output_audio=SimpleNamespace(data=base64.b64encode(b"RIFFfake").decode()))

    monkeypatch.setattr(genai, "Client", FakeClient)
    monkeypatch.setattr(service, "_change_audio_speed", lambda src, dst, rate: dst.write_bytes(src.read_bytes() + str(rate).encode()))
    out = service._generate_gemini_tts(tmp_path, "안녕", AppSettings(gemini_api_key="k"))
    assert out.read_bytes() == b"RIFFfake1.2"
    assert calls["generation_config"] == {"speech_config": [{"voice": "Kore"}]}
    assert not (tmp_path / "temp_tts_raw.wav").exists()


def test_llm_key_prefers_gemini_only_with_base_url():
    from app.core.settings import AppSettings

    assert AppSettings(openai_api_key="o", gemini_api_key="g").llm_api_key == "o"
    assert AppSettings(openai_api_key="o", gemini_api_key="g", llm_base_url="u").llm_api_key == "g"



def test_cloudflare_retries_transient_400(tmp_path, monkeypatch):
    import base64
    from app.core.settings import AppSettings
    from app.production import service

    codes = iter([400, 200])

    def fake_post(*a, **kw):
        code = next(codes)
        return SimpleNamespace(status_code=code, raise_for_status=lambda: None,
                               json=lambda: {"result": {"image": base64.b64encode(b"img").decode()}})

    monkeypatch.setattr(service.httpx, "post", fake_post)
    monkeypatch.setattr(service.time, "sleep", lambda s: None)
    target = tmp_path / "x.png"
    service._generate_cloudflare_image(AppSettings(cloudflare_account_id="a", cloudflare_api_token="t"), "p", target)
    assert target.read_bytes() == b"img"


def test_concept_prompt_uses_selected_style(tmp_path, monkeypatch):
    import json as _json
    from app.core.settings import AppSettings
    from app.production import service

    (tmp_path / "final_script.md").write_text("첫 문장입니다. 두 번째 문장입니다.", encoding="utf-8")
    seen = {}
    reply = {"concept_kit": {"visual_style": "x"}, "video_scenes": [
        {"scene_id": 1, "start": 0, "end": 2, "narration": "첫 문장입니다."}]}

    def create(**kw):
        seen["prompt"] = kw["messages"][0]["content"]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=_json.dumps(reply)))])

    monkeypatch.setattr(service, "make_llm_client", lambda settings: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    monkeypatch.setattr(service, "calibrate_scenes_with_stt", lambda scenes, stt, dur: scenes)
    kit, _ = service.generate_concept_kit_and_video_scenes(tmp_path, AppSettings(), "webtoon")
    assert "Korean webtoon" in seen["prompt"] and "clay" not in seen["prompt"].lower()
    assert kit.style_id == "webtoon"
    assert _json.loads((tmp_path / "concept_kit.json").read_text(encoding="utf-8"))["style_id"] == "webtoon"


def test_unknown_style_rejected():
    import pytest
    from app.production.styles import get_style

    with pytest.raises(ValueError):
        get_style("nope")


def test_fallback_llm_moves_to_next_model_on_quota():
    import httpx
    from openai import RateLimitError
    from app.references.openai_clients import FallbackLLM

    tried = []

    def create(model, **kw):
        tried.append(model)
        if model != "lite":
            raise RateLimitError("quota", response=httpx.Response(429, request=httpx.Request("POST", "http://x")), body=None)
        return "ok"

    llm = FallbackLLM("k", "http://x", ["primary", "lite", "never"])
    llm._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    assert llm.chat.completions.create(model="primary", messages=[]) == "ok"
    assert tried == ["primary", "lite"]


def test_fallback_llm_does_not_retry_bad_request():
    import httpx
    import pytest
    from openai import BadRequestError
    from app.references.openai_clients import FallbackLLM

    def create(model, **kw):
        raise BadRequestError("bad", response=httpx.Response(400, request=httpx.Request("POST", "http://x")), body=None)

    llm = FallbackLLM("k", "http://x", ["lite"])
    llm._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with pytest.raises(BadRequestError):
        llm.chat.completions.create(model="primary", messages=[])


def test_kenburns_moves_rotate_without_repeating_neighbors():
    from app.production.service import _kenburns_motion

    moves = [_kenburns_motion(i, 150) for i in range(1, 11)]
    assert all(a != b for a, b in zip(moves, moves[1:]))
    assert moves[0] == moves[5]
