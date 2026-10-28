"""Word-level subtitle timing.

Segment timestamps from Whisper span 3–7 s and often two sentences, so subtitles timed by splitting a
segment by character count drift from the voice. Here every script word gets its own start/end from
Whisper's word timestamps, then words are grouped into short one-line chunks for the Shorts layout.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

WORDS_CACHE_FILE = "subtitle_words.json"
MAX_LINE_CHARS = 12  # one line at subtitle size (~820px wide)
PAUSE_SPLIT = 0.35  # a breath longer than this starts a new chunk
LINE_END = tuple(".?!,~…")
NUMBER_END = re.compile(r"[\d만억조천백]$")  # "230만" + "개의": never split a number from its unit


def transcribe_words(audio_path: Path, model: str, device: str) -> list[dict]:
    """[{text, start, end}] per spoken word, cached next to the audio (CPU Whisper takes ~30 s)."""
    cache = audio_path.parent / WORDS_CACHE_FILE
    stamp = f"{audio_path.stat().st_size}:{audio_path.stat().st_mtime_ns}"
    try:
        cached = json.loads(cache.read_text(encoding="utf-8"))
        if cached.get("audio") == stamp:
            return cached["words"]
    except (OSError, ValueError):
        pass
    from app.references.openai_clients import _load_whisper

    segments, _ = _load_whisper(model, device).transcribe(str(audio_path), language="ko", word_timestamps=True)
    words = [{"text": w.word.strip(), "start": w.start, "end": w.end} for s in segments for w in (s.words or []) if w.word.strip()]
    cache.write_text(json.dumps({"audio": stamp, "words": words}, ensure_ascii=False), encoding="utf-8")
    return words


def _time_at(timeline: list[tuple[int, int, float, float]], pos: float, starting: bool) -> float:
    """Time at a character offset, interpolating inside the spoken word that holds it.
    A word that starts exactly where a spoken word ends belongs to the next spoken word."""
    for c0, c1, t0, t1 in timeline:
        if pos < c1 or (not starting and pos == c1):
            return t0 + (t1 - t0) * (max(pos, c0) - c0) / max(c1 - c0, 1)
    return timeline[-1][3]


def assign_word_times(blocks: list[dict], spoken: list[dict]) -> list[dict]:
    """Give each word of the (LLM-corrected) script text a time from the spoken words.

    Script and Whisper words differ in spelling and splitting ("심리향" vs "심리학"), so within each block
    they are matched by relative character position rather than one-to-one.
    """
    out: list[dict] = []
    for i, block in enumerate(blocks):
        script_words = block["text"].split()
        if not script_words:
            continue
        upper = blocks[i + 1]["start"] if i + 1 < len(blocks) else float("inf")
        heard = [w for w in spoken if block["start"] - 0.05 <= (w["start"] + w["end"]) / 2 < upper]
        if not heard:  # nothing recognised here: spread the words evenly over the block
            step = (block["end"] - block["start"]) / len(script_words)
            out += [{"text": t, "start": block["start"] + k * step, "end": block["start"] + (k + 1) * step} for k, t in enumerate(script_words)]
            continue
        timeline, pos = [], 0
        for w in heard:
            timeline.append((pos, pos + len(w["text"]), w["start"], w["end"]))
            pos += len(w["text"])
        heard_chars = pos
        script_chars = sum(len(t) for t in script_words)
        done = 0
        for t in script_words:
            a, b = done / script_chars * heard_chars, (done + len(t)) / script_chars * heard_chars
            out.append({"text": t, "start": round(_time_at(timeline, a, True), 3), "end": round(_time_at(timeline, b, False), 3)})
            done += len(t)
    return out


def one_line_chunks(words: list[dict], max_chars: int = MAX_LINE_CHARS) -> list[dict]:
    """Group timed words into one-line subtitles; each keeps its words so the spoken one can be highlighted."""
    groups: list[list[dict]] = []
    for w in words:
        cur = groups[-1] if groups else None
        if cur is not None and NUMBER_END.search(cur[-1]["text"]):
            cur.append(w)  # may run a few characters long; the renderer shrinks the font to keep one line
        elif (
            cur is None
            or len(" ".join(x["text"] for x in cur + [w])) > max_chars
            or cur[-1]["text"].endswith(LINE_END)
            or w["start"] - cur[-1]["end"] > PAUSE_SPLIT
        ):
            groups.append([w])
        else:
            cur.append(w)
    chunks = []
    for i, g in enumerate(groups):
        nxt = groups[i + 1][0]["start"] if i + 1 < len(groups) else None
        # hold through short pauses so the screen doesn't flicker empty between chunks
        end = nxt if nxt is not None and nxt - g[-1]["end"] < 0.6 else g[-1]["end"] + 0.3
        chunks.append({"start": g[0]["start"], "end": round(end, 3), "text": " ".join(x["text"] for x in g), "words": g})
    return chunks


if __name__ == "__main__":
    blocks = [{"start": 0.0, "end": 3.0, "text": "그런데 심리학 연구에서 밝혀낸 반전!"}, {"start": 3.0, "end": 4.0, "text": "첫째"}]
    heard = [
        {"text": "그런데", "start": 0.0, "end": 0.4}, {"text": "심리향", "start": 0.5, "end": 1.0},
        {"text": "연구에서", "start": 1.0, "end": 1.4}, {"text": "밝혀는", "start": 1.4, "end": 1.8},
        {"text": "반전!", "start": 1.9, "end": 2.4}, {"text": "첫째", "start": 3.2, "end": 3.6},
    ]
    timed = assign_word_times(blocks, heard)
    assert [w["text"] for w in timed][:2] == ["그런데", "심리학"] and timed[1]["start"] == 0.5
    lines = one_line_chunks(timed)
    assert all(len(c["text"]) <= MAX_LINE_CHARS or len(c["words"]) == 1 for c in lines)
    assert lines[-1]["text"] == "첫째" and lines[-2]["text"].endswith("반전!")
    nums = one_line_chunks([{"text": t, "start": k, "end": k + 0.9} for k, t in enumerate("피라미드가 230만 개의 돌을".split())])
    assert [c["text"] for c in nums] == ["피라미드가 230만 개의", "돌을"]
    print("ok", [c["text"] for c in lines])
