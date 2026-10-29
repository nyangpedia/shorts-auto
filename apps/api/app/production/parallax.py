"""Free 2.5D camera move: a depth map splits the still into near and far, and near things move more.

Depth comes from Depth Anything V2 (small, ONNX, Apache-2.0), downloaded once (~100 MB) to the
Hugging Face cache and run on CPU in about 2 s per picture. Each frame is a backward warp of the
picture: output pixel p samples the picture at p / scale(depth) - shift * depth, so the foreground
grows and slides against a steadier background.
"""
from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

DEPTH_REPO = "onnx-community/depth-anything-v2-small"
OUT_W, OUT_H, FPS = 1080, 1920, 30
_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)

# (zoom over the clip, extra zoom for the nearest things, sideways drift, vertical drift); picked by scene id
# so neighbouring scenes don't all move the same way
_MOVES = [
    (0.06, 0.07, 0.035, 0.0),
    (0.05, 0.06, -0.035, 0.01),
    (0.03, 0.08, 0.0, -0.025),
    (0.06, 0.05, -0.025, -0.015),
]


@lru_cache(maxsize=1)
def _depth_session():
    import onnxruntime as ort
    from huggingface_hub import hf_hub_download

    return ort.InferenceSession(hf_hub_download(DEPTH_REPO, "onnx/model.onnx"), providers=["CPUExecutionProvider"])


def depth_map(picture: Image.Image) -> np.ndarray:
    """0 (far) … 1 (near), same size as the picture, lightly blurred so edges don't tear."""
    session = _depth_session()
    w = 518
    h = max(14, round(w * picture.height / picture.width / 14) * 14)
    x = (np.asarray(picture.resize((w, h), Image.BICUBIC), np.float32) / 255 - _MEAN) / _STD
    raw = session.run(None, {session.get_inputs()[0].name: x.transpose(2, 0, 1)[None]})[0][0]
    raw = (raw - raw.min()) / max(float(raw.max() - raw.min()), 1e-6)
    from PIL import ImageFilter

    small = Image.fromarray((raw * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))
    return np.asarray(small.resize(picture.size, Image.BILINEAR), np.float32) / 255


def _sample(image: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Bilinear lookup of image at float pixel coords (edges repeat)."""
    import cv2

    return cv2.remap(image, x, y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def make_parallax_video(scene_id: int, image_path: Path, video_path: Path, duration: float) -> None:
    picture = Image.open(image_path).convert("RGB")
    # cover the 9:16 frame with a little margin so the move never shows an edge
    scale = max(OUT_W / picture.width, OUT_H / picture.height) * 1.12
    picture = picture.resize((round(picture.width * scale), round(picture.height * scale)), Image.LANCZOS)
    image = np.asarray(picture)
    depth = depth_map(picture)
    h, w = depth.shape
    zoom, dolly, drift_x, drift_y = _MOVES[(scene_id - 1) % len(_MOVES)]

    # output pixel grid, centred, in picture pixels
    ys, xs = np.mgrid[0:OUT_H, 0:OUT_W].astype(np.float32)
    ux, uy = xs - OUT_W / 2, ys - OUT_H / 2
    cx, cy = w / 2, h / 2
    frames = max(1, round(duration * FPS))

    command = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{OUT_W}x{OUT_H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "18", "-pix_fmt", "yuv420p", str(video_path)]
    with subprocess.Popen(command, stdin=subprocess.PIPE) as ffmpeg:
        for i in range(frames):
            t = i / max(frames - 1, 1)
            t = t * t * (3 - 2 * t)  # ease in and out
            d = _sample(depth, cx + ux, cy + uy)
            for _ in range(2):  # refine: look up depth where the pixel actually comes from
                s = 1 + zoom * t + dolly * t * d
                sx = cx + ux / s - drift_x * t * d * w
                sy = cy + uy / s - drift_y * t * d * h
                d = _sample(depth, sx, sy)
            frame = _sample(image, sx, sy)
            ffmpeg.stdin.write(frame.tobytes())
        ffmpeg.stdin.close()
    if ffmpeg.returncode:
        raise RuntimeError(f"ffmpeg failed while writing {video_path.name}")
