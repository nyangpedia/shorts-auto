"""Scene images. Each provider writes one vertical image for a prompt; failures surface as errors
instead of a silent placeholder, so a broken key or quota shows up in the UI."""
from __future__ import annotations

import base64
import logging
import subprocess
import time
import json
from pathlib import Path

import httpx

from app.core import usage
from app.core.settings import AppSettings
from app.production.paths import find_scene, load_scene_list, scene_asset

logger = logging.getLogger(__name__)

# ── Cloudflare Workers AI (free: 10k neurons/day ≈ 95 FLUX.2 klein images) ──

CLOUDFLARE_RETRY_STATUSES = (400, 429, 500, 502, 503, 504)


def _post_cloudflare(settings: AppSettings, model: str, attempts: int = 3, **request) -> httpx.Response | None:
    """The model's reply, or None if it never answered. Workers AI intermittently returns 400 (or stalls)
    for a prompt that succeeds on the next try."""
    resp = None
    for attempt in range(attempts):
        try:
            resp = httpx.post(
                f"https://api.cloudflare.com/client/v4/accounts/{settings.cloudflare_account_id}/ai/run/{model}",
                headers={"Authorization": f"Bearer {settings.cloudflare_api_token}"},
                timeout=60.0,
                **request,
            )
        except httpx.TimeoutException:
            # A stalled model rarely recovers within seconds; let the caller fall back instead of waiting 3x.
            logger.warning("Cloudflare %s timed out", model)
            return None
        if resp.status_code not in CLOUDFLARE_RETRY_STATUSES or attempt == attempts - 1 or _quota_exhausted(resp):
            break
        time.sleep(2 * (attempt + 1))
    return resp


class ImageQuotaExhausted(RuntimeError):
    """Cloudflare said the free allowance is used up: every further picture today would fail the same way."""


def _quota_exhausted(resp: httpx.Response | None) -> bool:
    """Code 4006 is "daily free allocation used up". Other 429s are short rate limits worth retrying."""
    if resp is None or resp.status_code != 429:
        return False
    try:
        return any(e.get("code") == 4006 for e in resp.json().get("errors", []))
    except ValueError:
        return False


def _succeeded(resp: httpx.Response | None) -> bool:
    return resp is not None and resp.status_code == 200 and bool(resp.json().get("success"))


def _generate_cloudflare_image(settings: AppSettings, prompt: str, target: Path) -> None:
    # FLUX.2 klein takes a size, so scenes come out 9:16 natively;
    # flux-1-schnell (square only, center-cropped later) is the fallback.
    if not (settings.cloudflare_account_id and settings.cloudflare_api_token):
        raise RuntimeError("Cloudflare 계정 ID / API 토큰이 없습니다. 설정 화면에서 넣어주세요.")
    resp = _post_cloudflare(
        settings,
        "@cf/black-forest-labs/flux-2-klein-4b",
        files={"prompt": (None, f"{prompt[:1900]}, vertical composition"), "width": (None, "768"), "height": (None, "1344")},
    )
    if _quota_exhausted(resp):
        _report_exhausted()
    if not _succeeded(resp):
        logger.warning("FLUX.2 klein failed (%s); falling back to flux-1-schnell", resp.status_code if resp else "timeout")
        resp = _post_cloudflare(
            settings,
            "@cf/black-forest-labs/flux-1-schnell",
            # Square output gets center-cropped to 9:16, so keep the subject in the middle third.
            json={"prompt": f"{prompt[:1850]}, subject centered in frame, nothing important near left or right edges", "steps": 4},
        )
    if resp is None:
        raise RuntimeError("Cloudflare 이미지 서버가 응답하지 않습니다. 잠시 후 다시 시도해주세요.")
    if _quota_exhausted(resp):
        _report_exhausted()
    if resp.status_code == 429:
        raise RuntimeError("Cloudflare 요청이 잠깐 몰렸습니다. 1분쯤 뒤 다시 시도해주세요.")
    resp.raise_for_status()
    target.write_bytes(base64.b64decode(resp.json()["result"]["image"]))
    usage.record("image")


def _report_exhausted():
    usage.mark_exhausted("image")
    raise ImageQuotaExhausted(
        "Cloudflare 무료 이미지 한도(하루 약 70장)를 다 썼습니다. Cloudflare는 지난 24시간 사용량으로 계산해서, "
        "어제 많이 만든 시간대가 지나면 다시 풀립니다.")


# ── Gemini image (free tier where available) ───────────────────────────────

def _generate_gemini_image(settings: AppSettings, prompt: str, target: Path) -> None:
    from google import genai
    from google.genai import types

    if not settings.gemini_api_key:
        raise RuntimeError("Gemini API 키가 없습니다. 설정 화면에서 넣어주세요.")
    reply = genai.Client(api_key=settings.gemini_api_key).models.generate_content(
        model=settings.gemini_image_model,
        contents=f"{prompt} Vertical 9:16 portrait composition.",
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )
    for part in reply.candidates[0].content.parts:
        if part.inline_data and part.inline_data.data:
            target.write_bytes(part.inline_data.data)
            return
    raise RuntimeError("Gemini가 이미지를 돌려주지 않았습니다.")


# ── OpenAI GPT Image (paid) ─────────────────────────────────────────────────

OPENAI_IMAGE_MODEL = "gpt-image-2.5-flare"  # OpenAI's everyday image model (replaces DALL·E 3)


def _generate_openai_image(settings: AppSettings, prompt: str, target: Path) -> None:
    from openai import OpenAI

    if not settings.openai_api_key:
        raise RuntimeError("OpenAI API 키가 없습니다. 설정 화면에서 넣어주세요. (유료)")
    reply = OpenAI(api_key=settings.openai_api_key).images.generate(
        model=OPENAI_IMAGE_MODEL, prompt=prompt[:4000], size="1024x1536", quality="medium", n=1,
    )
    target.write_bytes(base64.b64decode(reply.data[0].b64_json))
    usage.record("image")


# ── Higgsfield (paid, via its CLI) ──────────────────────────────────────────

HIGGSFIELD_ALIASES = {
    "grok_imagine_1_5_lite": "grok_video_v15_lite",
    "grok_imagine1_5_lite": "grok_video_v15_lite",
    "grok_1_5_lite": "grok_video_v15_lite",
    "grok_video_v15": "grok_video_v15_lite",
    "minimax": "minimax_h3",
    "minimax_h3_lite": "minimax_h3",
}


def higgsfield_run(model: str, prompt: str, *, extra: list[str] | None = None, timeout_min: int = 15) -> str:
    """Run `higgsfield generate create` and return the result URL."""
    model = HIGGSFIELD_ALIASES.get(model, model)
    cmd = ["higgsfield", "generate", "create", model, "--prompt", prompt, "--aspect-ratio", "9:16", "--wait", "--json", *(extra or [])]
    done = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_min * 60)
    if done.returncode != 0:
        raise RuntimeError(f"Higgsfield 실행 실패 ({done.returncode}): {(done.stderr or done.stdout)[:400]}")
    try:
        result = json.loads(done.stdout)
        result = result[0] if isinstance(result, list) else result
        url = result.get("result_url") or result.get("output_url") or result.get("url")
    except (ValueError, AttributeError, IndexError) as exc:
        raise RuntimeError(f"Higgsfield 결과를 읽지 못했습니다: {done.stdout[:300]}") from exc
    if not url:
        raise RuntimeError(f"Higgsfield 결과에 파일 주소가 없습니다: {done.stdout[:300]}")
    return str(url)


def download(url: str, target: Path, timeout: float = 120.0) -> None:
    resp = httpx.get(url, timeout=timeout, follow_redirects=True)
    if resp.status_code != 200:
        raise RuntimeError(f"결과 파일을 내려받지 못했습니다 ({resp.status_code})")
    target.write_bytes(resp.content)


def _generate_higgsfield_image(model: str, prompt: str, target: Path) -> None:
    sharper = any(k in model for k in ("gpt", "seedream"))
    download(higgsfield_run(model, prompt, extra=["--resolution", "2k" if sharper else "1k"]), target, timeout=90.0)


# ── dispatch ────────────────────────────────────────────────────────────────

def draw_image(settings: AppSettings, model: str, prompt: str, target: Path) -> None:
    if model == "cloudflare":
        _generate_cloudflare_image(settings, prompt, target)
    elif model == "gemini_image":
        _generate_gemini_image(settings, prompt, target)
    elif model in ("gpt_image", "openai_image", "dall-e-3"):  # "dall-e-3" kept so old saved choices still work
        _generate_openai_image(settings, prompt, target)
    else:
        _generate_higgsfield_image(model or "nano_banana_pro", prompt, target)


def generate_scene_image_for_project(project_dir: Path, scene_id: int, settings: AppSettings, model_name: str = "cloudflare") -> Path:
    scene = find_scene(load_scene_list(project_dir), scene_id)
    prompt = scene.get("start_image_prompt") or f"Vertical 9:16 illustration for: {scene.get('narration', '')}"
    image = scene_asset(project_dir, scene_id, "start")
    # A new picture invalidates the clip and last frame made from the old one.
    scene_asset(project_dir, scene_id, "video").unlink(missing_ok=True)
    scene_asset(project_dir, scene_id, "final").unlink(missing_ok=True)
    draw_image(settings, model_name, prompt, image)
    return image
