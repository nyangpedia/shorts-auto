"""Draw the style-picker samples: one shared scene in every visual style.

Writes apps/web/public/styles/<style_id>.jpg (small, ~20 KB each). Uses 7 Cloudflare images.
Run from apps/api:  .venv/Scripts/python ../../tools/dev/style_samples.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

from app.core.settings import load_settings  # noqa: E402
from app.main import find_repo_root  # noqa: E402
from app.production.images import draw_image  # noqa: E402
from app.production.styles import VISUAL_STYLES  # noqa: E402

# One scene that shows what each style does with people, objects, scale and a setting.
SCENE = (
    "Medium-wide shot: a young researcher in a yellow raincoat stands on the deck of a small boat at sea, "
    "pointing at a giant whale surfacing beside the boat, with a cutaway cross-section below the waterline "
    "showing the ocean getting darker with depth"
)
OUT = find_repo_root() / "apps" / "web" / "public" / "styles"


def main(only: list[str]) -> None:
    settings = load_settings(find_repo_root())
    OUT.mkdir(parents=True, exist_ok=True)
    for style_id, style in VISUAL_STYLES.items():
        if only and style_id not in only:
            continue
        prompt = (f"{style['style']}, vertical 9:16 portrait. {SCENE}. {style['texture']}, {style['lighting']}. "
                  "no text, no lettering, no numbers, no logos, no watermark")
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw.png"
            draw_image(settings, "cloudflare", prompt, raw)
            picture = Image.open(raw).convert("RGB")
            picture.thumbnail((240, 420))
            picture.save(OUT / f"{style_id}.jpg", quality=82)
        print("drew", style_id)


if __name__ == "__main__":
    main(sys.argv[1:])
