"""2.5D move: near pixels travel further than far ones, and a failing depth model falls back to Ken Burns."""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.production import motion, parallax


def near_bottom(picture: Image.Image) -> np.ndarray:
    """Fake depth: top row far (0), bottom row near (1)."""
    return np.repeat(np.linspace(0, 1, picture.height, dtype=np.float32)[:, None], picture.width, axis=1)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_near_things_move_more(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(parallax, "depth_map", near_bottom)
    line = np.zeros((1344, 768, 3), np.uint8)
    line[:, 380:388] = 255  # one white line through the middle: zoom leaves it in place, sideways drift doesn't
    Image.fromarray(line).save(tmp_path / "in.png")
    parallax.make_parallax_video(1, tmp_path / "in.png", tmp_path / "out.mp4", 0.5)  # move 1 drifts sideways

    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(tmp_path / "out.mp4"), "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, 1920, 1080)
    first, last = frames[0], frames[-1]

    def moved(row: int) -> int:
        return abs(int(np.argmax(last[row])) - int(np.argmax(first[row])))

    assert moved(100) <= 8, moved(100)  # far: about stays (line sits half a pixel off centre, zoom grows that)
    assert moved(1800) >= 30, moved(1800)  # near: slides

def test_depth_failure_falls_back_to_camera_move(tmp_path: Path, monkeypatch):
    (tmp_path / "scenes").mkdir()
    Image.new("RGB", (8, 8)).save(tmp_path / "scenes" / "scene_01_start.png")
    (tmp_path / "video_scenes.json").write_text(json.dumps([{"scene_id": 1}]), encoding="utf-8")

    def broken(*args):
        raise RuntimeError("no network")

    used = []
    monkeypatch.setattr(motion, "make_parallax_video", broken)
    monkeypatch.setattr(motion, "_make_kenburns_video", lambda sid, pic, clip, dur: (used.append(sid), clip.write_bytes(b"v")))
    monkeypatch.setattr(motion, "grab_last_frame", lambda clip, frame: frame.write_bytes(b"f"))
    motion.generate_scene_video_for_project(tmp_path, 1, settings=None, model_name="parallax")
    assert used == [1]
