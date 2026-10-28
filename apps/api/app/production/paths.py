"""Where a project's production artifacts live, and reading/writing the scene list.

File names are the on-disk format of existing projects, so they must not change.
"""
from __future__ import annotations

import json
from pathlib import Path

TTS_AUDIO_FILENAME = "output_1.2x.wav"
RAW_STT_FILENAME = "raw_stt.json"
SCENE_DATA_FILENAME = "scene_data.json"
CONCEPT_KIT_FILENAME = "concept_kit.json"
VIDEO_SCENES_FILENAME = "video_scenes.json"
SCENES_DIR_NAME = "scenes"
FINAL_SCRIPT_FILENAME = "final_script.md"

FPS = 30
NARRATION_SPEED = 1.2


def scene_asset(project_dir: Path, scene_id: int, kind: str) -> Path:
    """kind: "start" / "final" / "end" → .png, "video" → .mp4."""
    ext = "mp4" if kind == "video" else "png"
    folder = project_dir / SCENES_DIR_NAME
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"scene_{scene_id:02d}_{kind}.{ext}"


def read_final_script(project_dir: Path) -> str:
    path = project_dir / FINAL_SCRIPT_FILENAME
    if not path.exists():
        raise FileNotFoundError("확정된 대본(final_script.md)이 없습니다. 대본 단계를 먼저 끝내주세요.")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("확정된 대본이 비어 있습니다.")
    return text


def load_scene_list(project_dir: Path) -> list[dict]:
    path = project_dir / VIDEO_SCENES_FILENAME
    if not path.exists():
        raise FileNotFoundError("씬 구성이 없습니다. 음성·화풍 단계에서 씬을 먼저 구성해주세요.")
    return json.loads(path.read_text(encoding="utf-8"))


def save_scene_list(project_dir: Path, scenes: list[dict]) -> None:
    (project_dir / VIDEO_SCENES_FILENAME).write_text(json.dumps(scenes, ensure_ascii=False, indent=2), encoding="utf-8")


def find_scene(scenes: list[dict], scene_id: int) -> dict:
    for scene in scenes:
        if scene.get("scene_id") == scene_id:
            return scene
    raise ValueError(f"{scene_id}번 씬이 없습니다.")


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
