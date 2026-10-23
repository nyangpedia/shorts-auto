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


def test_stock_query_drops_style_words():
    from app.production.service import _stock_query

    prompt = "Claymation style vertical 9:16 portrait of a golden retriever running on the beach, cinematic lighting"
    assert _stock_query(prompt) == "golden retriever running beach"
    assert _stock_query("cinematic 3D render") == "abstract background"


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


def test_stock_prefers_portrait_pixabay_video(monkeypatch):
    from app.core.settings import AppSettings
    from app.production import service

    def v(w, h, tag):
        return {"videos": {"large": {"url": "", "width": 0, "height": 0},
                           "medium": {"url": f"{tag}-m", "width": w, "height": h},
                           "small": {"url": f"{tag}-s", "width": w // 2, "height": h // 2}}}

    monkeypatch.setattr(service, "_http_json", lambda url, params, headers=None: {"hits": [v(1920, 1080, "land"), v(1080, 1920, "port")]})
    s = AppSettings(pixabay_api_key="k")
    assert service._stock_media_url(s, "video", "q", 0) == "port-m"
    assert service._stock_media_url(s, "video", "q", 1) == "land-m"
