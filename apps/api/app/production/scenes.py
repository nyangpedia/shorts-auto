"""Scene planning: cut the script into ~2.5 s beats, have the LLM storyboard each beat in the chosen
style, and time every scene against the narration actually spoken."""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.core.settings import AppSettings
from app.production.llm import ask_json
from app.production.media import media_duration
from app.production.models import ConceptKit, ContinuityState, VideoSceneItem
from app.production.paths import (
    CONCEPT_KIT_FILENAME,
    FPS,
    SCENE_DATA_FILENAME,
    TTS_AUDIO_FILENAME,
    VIDEO_SCENES_FILENAME,
    read_final_script,
    write_json,
)
from app.production.styles import get_style

# ── cutting the script into beats ───────────────────────────────────────────

BEAT_SOFT = 12  # from this length a natural pause ends the beat
BEAT_MAX = 22  # characters ≈ 2.5–3 s of 1.2x narration; Shorts that hold attention cut every 2-3 s
BEAT_MIN = 8  # shorter pieces never stand alone
_SENTENCES = re.compile(r"(?<=[.?!])\s+|\n+")
# Natural pause points inside a Korean sentence: a comma, or a connective ending (…는데, …지만, …하고 …).
_SOFT_BREAK = re.compile(r"(,|는데|은데|지만|면서|으며|하며|거나|으나|했고|하고|되고|이고)$")
_NUMBER_TAIL = re.compile(r"[\d만억조천백]$")


def _cut_sentence(sentence: str) -> list[str]:
    pieces, line = [], ""
    for word in sentence.split():
        if line and len(f"{line} {word}") > BEAT_MAX and not _NUMBER_TAIL.search(line):
            pieces.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
        if len(line) >= BEAT_SOFT and _SOFT_BREAK.search(line):
            pieces.append(line)
            line = ""
    if line:
        pieces.append(line)
    # A stub stays inside its own sentence: "첫째로," leads into what follows, "보일까요?" closes what came before.
    if len(pieces) > 1 and len(pieces[0]) < BEAT_MIN:
        pieces[1] = f"{pieces.pop(0)} {pieces[0]}"
    if len(pieces) > 1 and len(pieces[-1]) < BEAT_MIN:
        tail = pieces.pop()
        pieces[-1] = f"{pieces[-1]} {tail}"
    return pieces


def script_beats(script: str) -> list[str]:
    beats: list[str] = []
    for sentence in (s.strip() for s in _SENTENCES.split(script)):
        if not sentence:
            continue
        pieces = _cut_sentence(sentence)
        if len(pieces) == 1 and len(pieces[0]) < BEAT_MIN and beats:
            beats[-1] = f"{beats[-1]} {pieces[0]}"  # a tiny sentence ("놀랍죠?") rides on the previous beat
        else:
            beats.extend(pieces)
    return beats


# ── timing beats against the narration ─────────────────────────────────────

def beat_times(project_dir: Path, beats: list[str], settings: AppSettings) -> list[tuple[float, float]]:
    """(start, end) per beat from word-level timings of the spoken narration.

    Falls back to spreading beats by length when there is no narration yet.
    """
    audio = project_dir / TTS_AUDIO_FILENAME
    total = media_duration(audio) if audio.exists() else 0.0
    starts: list[float] | None = None
    blocks_path = project_dir / SCENE_DATA_FILENAME
    if audio.exists() and blocks_path.exists():
        try:
            from app.production.word_timing import assign_word_times, transcribe_words

            blocks = [b for scene in json.loads(blocks_path.read_text(encoding="utf-8")) for b in scene["text_blocks"]]
            words = assign_word_times(blocks, transcribe_words(audio, settings.whisper_model, settings.whisper_device))
            starts, k = [], 0
            for beat in beats:
                starts.append(words[min(k, len(words) - 1)]["start"])
                k += len(beat.split())
        except Exception:
            starts = None  # timing is a nicety; proportional spacing still gives a usable plan
    if total <= 0:
        total = max(1.0, sum(len(b) for b in beats) / 8.0)  # ~8 characters per second at 1.2x
    if starts is None:
        lengths = [len(b) for b in beats]
        starts, acc = [], 0
        for n in lengths:
            starts.append(total * acc / sum(lengths))
            acc += n
    starts[0] = 0.0
    ends = starts[1:] + [total]
    return [(round(s, 2), round(max(e, s + 0.5), 2)) for s, e in zip(starts, ends)]


# ── storyboard prompt ───────────────────────────────────────────────────────

def storyboard_prompt(beats: list[str], style: dict[str, str], seconds: float) -> str:
    lines = "\n".join(f"{i}. {b}" for i, b in enumerate(beats, 1))
    n = len(beats)
    return f"""너는 세로형 쇼츠의 스토리보드를 그리는 {style["role"]}다.
아래 내레이션은 약 {seconds:.0f}초 분량이고, 화면이 바뀌는 단위로 {n}줄로 잘려 있다.
줄마다 장면 하나씩, 정확히 {n}개의 장면을 순서대로 설계해라. 줄을 합치거나 빼거나 나누지 마라.

먼저 영상 전체의 시각 설계(concept_kit)를 정한다.
- 이 영상의 주인공(사람·캐릭터·사물 중 대본에 가장 맞는 하나)을 정하고, 알아볼 수 있는 외형을 구체적으로 정한다.
- 이야기가 벌어지는 공간과 색감을 정해서 장면이 바뀌어도 같은 세계로 보이게 한다.

그다음 장면마다 세 가지를 영어로 쓴다.
1) start_image_prompt — 이미지 생성 AI에게 줄 한 장의 그림 설명.
   - 맨 앞에 화풍을 쓴다: "{style["style"]}, vertical 9:16 portrait".
   - 그 줄의 내레이션이 말하는 핵심을 1초 안에 알아보게 하는 구체적인 장면을 화면 한가운데에 크게 둔다.
     추상적인 말은 눈에 보이는 상황이나 비유로 바꾼다.
   - 사람이 하는 행동을 말하는 줄에만 사람을 넣는다. 현상·사물·개념을 말하는 줄은 그 대상 자체를 크게 보여주고 사람을 넣지 않는다.
   - 주인공이 나오면 concept_kit에서 정한 외형을 매번 똑같은 단어로 다시 적는다. "a person", "a figure" 같은 뭉뚱그린 말은 쓰지 않는다.
   - 사람이 나오는 장면에서만 이 방식으로 그린다(이 문장 자체를 프롬프트에 옮겨 적지 말 것): {style["subject"]}.
   - 질감과 조명은 그대로 적는다: {style["texture"]}, {style["lighting"]}.
   - 손에 든 물건이나 도구는 실제로 쓰는 방식대로 잡고 있게 묘사한다.
   - 그림 안에는 어떤 글자도 없어야 한다. 끝에 반드시 "no text, no lettering, no numbers, no logos, no watermark"를 붙인다.
2) video_prompt — 이 그림에서 시작하는 한 문단짜리 움직임 설명: 시작 구도 → 끊김 없는 카메라 이동과 피사체의 변화({style["motion"]}) → 다음 장면으로 자연스럽게 넘어가는 마지막 구도. 컷 전환 없이.
3) continuity — camera(카메라 동선), subject_state(피사체 상태 변화), lighting(조명), handoff_description(다음 장면과 이어지는 방식) 각각 한 문장.

[내레이션]
{lines}

설명이나 마크다운 없이 아래 형태의 JSON 하나만 출력한다. scenes는 정확히 {n}개, scene_id는 1부터 {n}까지.
{{
  "concept_kit": {{
    "visual_style": "{style["style"]}, vertical 9:16",
    "color_and_lighting": "영어 한 문장",
    "core_objects": ["주인공과 그 외형", "핵심 사물", "배경 공간"],
    "camera_composition": "영어 한 문장",
    "continuity_rules": ["영어 한 문장", "영어 한 문장"]
  }},
  "scenes": [
    {{"scene_id": 1, "start_image_prompt": "...", "video_prompt": "...",
      "continuity": {{"camera": "...", "subject_state": "...", "lighting": "...", "handoff_description": "..."}}}}
  ]
}}"""


def generate_concept_kit_and_video_scenes(
    project_dir: Path,
    settings: AppSettings,
    style_id: str | None = None,
) -> tuple[ConceptKit, list[VideoSceneItem]]:
    style_id, style = get_style(style_id or settings.visual_style)
    beats = script_beats(read_final_script(project_dir))
    times = beat_times(project_dir, beats, settings)
    plan = ask_json(settings, storyboard_prompt(beats, style, times[-1][1]))

    kit = ConceptKit.model_validate(plan.get("concept_kit") or {})
    kit.style_id = style_id
    drawn = {int(s.get("scene_id", 0)): s for s in plan.get("scenes") or plan.get("video_scenes") or []}
    if len(drawn) < len(beats) / 2:
        raise ValueError(f"AI가 장면을 {len(beats)}개 중 {len(drawn)}개만 설계했습니다. 다시 시도해주세요.")

    scenes: list[VideoSceneItem] = []
    previous: dict = {}
    for i, (beat, (start, end)) in enumerate(zip(beats, times), 1):
        # A missing scene borrows its neighbour's look rather than failing the whole plan.
        board = drawn.get(i) or previous
        previous = board
        scenes.append(VideoSceneItem(
            scene_id=i, start=start, end=end, target_duration=round(end - start, 2),
            duration_frames=int((end - start) * FPS), narration=beat,
            start_image_prompt=board.get("start_image_prompt", ""),
            video_prompt=board.get("video_prompt", ""),
            continuity=ContinuityState.model_validate(board.get("continuity") or {}),
        ))

    write_json(project_dir / CONCEPT_KIT_FILENAME, kit.model_dump())
    write_json(project_dir / VIDEO_SCENES_FILENAME, [s.model_dump() for s in scenes])
    return kit, scenes
