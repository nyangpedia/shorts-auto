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
