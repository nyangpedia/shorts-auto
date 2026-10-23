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
