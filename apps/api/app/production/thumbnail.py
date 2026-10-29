"""Shorts thumbnail: one scene picture, darkened at the edges, with the title in big outlined type."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.production.paths import scene_asset

THUMBNAIL = "thumbnail.jpg"
SIZE = (1080, 1920)
FONT = Path(__file__).resolve().parents[3] / "video" / "fonts" / "Pretendard-Black.woff2"
LINE_WIDTH = 940  # px a title line may use
ACCENT = (255, 214, 10)  # last line, the payoff word(s)


def _lines(title: str, font: ImageFont.FreeTypeFont) -> list[str]:
    """Greedy word wrap by measured width; a word wider than a line gets its own line."""
    lines: list[str] = []
    for word in title.split():
        if lines and font.getlength(f"{lines[-1]} {word}") <= LINE_WIDTH:
            lines[-1] += f" {word}"
        else:
            lines.append(word)
    return lines


def _fit(title: str) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """Biggest size (down from 170px) at which the title fits in 3 lines."""
    for size in range(170, 79, -10):
        font = ImageFont.truetype(str(FONT), size)
        lines = _lines(title, font)
        if len(lines) <= 3 and all(font.getlength(l) <= LINE_WIDTH for l in lines):
            return font, lines
    return font, lines[:3]


def make_thumbnail(project_dir: Path, scene_id: int, title: str) -> Path:
    picture = scene_asset(project_dir, scene_id, "start")
    if not picture.exists():
        raise FileNotFoundError(f"{scene_id}번 씬에 이미지가 없습니다.")
    title = " ".join(title.split())
    if not title:
        raise ValueError("썸네일에 넣을 제목을 입력하세요.")

    canvas = ImageOps.fit(Image.open(picture).convert("RGB"), SIZE, Image.LANCZOS)
    # darken top and bottom so the text reads on any picture
    shade = Image.new("L", SIZE, 0)
    draw = ImageDraw.Draw(shade)
    for y in range(SIZE[1]):
        edge = min(y, SIZE[1] - y) / (SIZE[1] / 2)  # 0 at the edges, 1 in the middle
        draw.line([(0, y), (SIZE[0], y)], fill=int(170 * max(0.0, 1 - edge * 1.6)))
    canvas = Image.composite(Image.new("RGB", SIZE, (0, 0, 0)), canvas, shade)

    font, lines = _fit(title)
    draw = ImageDraw.Draw(canvas)
    step = int(font.size * 1.18)
    y = int(SIZE[1] * 0.16)  # upper third, clear of the Shorts UI at the bottom
    for i, line in enumerate(lines):
        color = ACCENT if i == len(lines) - 1 and len(lines) > 1 else (255, 255, 255)
        draw.text((SIZE[0] // 2, y), line, font=font, fill=color, anchor="mt",
                  stroke_width=max(8, font.size // 12), stroke_fill=(0, 0, 0))
        y += step

    out = project_dir / THUMBNAIL
    canvas.save(out, "JPEG", quality=88)  # YouTube takes up to 2 MB; this lands around 300–600 KB
    return out
