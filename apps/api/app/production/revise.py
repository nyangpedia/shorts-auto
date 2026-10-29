"""Rewrite one scene's prompts from the user's note ("인물을 더 크게, 배경은 밤으로"), then redraw it."""
from __future__ import annotations

import json
from pathlib import Path

from app.core.settings import AppSettings
from app.production.images import generate_scene_image_for_project
from app.production.llm import ask_json
from app.production.motion import generate_scene_video_for_project
from app.production.paths import CONCEPT_KIT_FILENAME, find_scene, load_scene_list, save_scene_list
from app.production.styles import get_style


def _picture_role(scene_id: int, chained: bool) -> str:
    if chained:
        return (f"{scene_id}번 장면은 앞 장면의 마지막 화면에서 이어지는 장면이다. 영상 AI는 앞 장면의 끝에서 출발해 "
                "이 그림에 '도착'한다. 그러니 그림은 시작 상태가 아니라, 내레이션이 말하는 결과가 가장 극적으로 드러난 도착 지점이어야 한다.")
    return f"{scene_id}번 장면은 혼자 시작하는 장면이다. 그림은 영상의 첫 화면, 즉 내레이션이 시작될 때의 상태다."


def revision_prompt(scene: dict, kit: dict, style: dict[str, str], note: str, target: str, chained: bool) -> str:
    wants_image = target in ("image", "prompt_image", "both")
    wants_video = target in ("video", "prompt_video", "both")
    fields = []
    if wants_image:
        fields.append('"start_image_prompt": "새 그림 설명(영어)"')
    if wants_video:
        fields.append('"video_prompt": "새 움직임 설명(영어, 한 문단)"')
    video_rule = ""
    if wants_video:
        video_rule = (
            "- video_prompt: " + ("앞 장면의 마지막 구도에서 출발해 카메라가 끊김 없이 움직여 이 장면의 그림에 정확히 안착하는 한 문단."
                                  if chained else "이 장면의 그림에서 출발해 카메라와 피사체가 자연스럽게 움직이는 한 문단.")
            + f" 움직임 느낌: {style['motion']}, 컷 전환 없이.\n"
        )
    return f"""너는 쇼츠 영상의 장면을 고치는 감독이다. 사용자의 수정 요청을 반드시 반영해서 이 장면의 프롬프트를 처음부터 다시 써라.

[장면]
- 내레이션: {scene.get("narration", "")}
- 지금 그림 설명: {scene.get("start_image_prompt", "")}
- 지금 움직임 설명: {scene.get("video_prompt", "")}
- 영상 전체 화풍: {kit.get("visual_style") or style["style"]}
- 주인공·핵심 사물: {", ".join(kit.get("core_objects") or [])}
- {_picture_role(scene.get("scene_id", 0), chained)}

[사용자 수정 요청 — 무엇보다 우선]
"{note}"

[다시 쓰는 규칙]
- 요청과 어긋나는 예전 구도·동작·자세는 남기지 말고 지운다.
- 요청한 핵심 동작이나 변화를 문장 맨 앞에 분명하게 쓴다.
- 물건이나 도구는 실제로 쓰는 부위를 실제로 쓰는 방식대로 잡거나 닿게 쓴다(손잡이를 잡고, 입구로 따르고…). 허공을 짚거나 엉뚱한 면을 대는 구도는 금지.
- 주인공은 위에 적힌 외형 그대로 이름 붙여 쓴다. 뭉뚱그린 말로 바꾸지 않는다.
- 내레이션의 핵심이 한눈에 보이는 장면을 화면 가운데에 둔다.
- 화풍 유지: {style["style"]}, vertical 9:16 portrait, {style["texture"]}, {style["lighting"]}.
- start_image_prompt 끝에는 "no text, no lettering, no numbers, no logos, no watermark"를 붙인다.
{video_rule}
설명 없이 JSON 하나만 출력한다: {{{", ".join(fields)}}}"""


def refine_and_regenerate_scene(
    project_dir: Path,
    scene_id: int,
    feedback: str,
    target: str,
    settings: AppSettings,
    model_name: str | None = None,
    duration: int = 5,
    multi_shots: bool = False,
    match_prev_frame: bool = True,
) -> None:
    """target: "image" / "video" / "both" redraw after rewriting; "prompt_image" / "prompt_video" only rewrite."""
    scenes = load_scene_list(project_dir)
    scene = find_scene(scenes, scene_id)
    kit_path = project_dir / CONCEPT_KIT_FILENAME
    kit = json.loads(kit_path.read_text(encoding="utf-8")) if kit_path.exists() else {}
    style = get_style(kit.get("style_id") or settings.visual_style)[1]
    chained = scene_id > 1 and match_prev_frame

    rewritten = ask_json(settings, revision_prompt(scene, kit, style, feedback, target, chained))
    for field in ("start_image_prompt", "video_prompt"):
        if isinstance(rewritten.get(field), str) and rewritten[field].strip():
            scene[field] = rewritten[field].strip()
    scene["last_feedback"] = feedback
    if target in ("image", "prompt_image", "both"):
        scene["last_image_feedback"] = feedback
    if target in ("video", "prompt_video", "both"):
        scene["last_video_feedback"] = feedback
    save_scene_list(project_dir, scenes)

    if target in ("image", "both"):
        generate_scene_image_for_project(project_dir, scene_id, settings, model_name=model_name or "cloudflare")
    if target in ("video", "both"):
        generate_scene_video_for_project(
            project_dir, scene_id, settings, model_name=model_name or "parallax",
            duration=duration, match_prev_frame=match_prev_frame,
        )


def update_scene_prompts_for_project(
    project_dir: Path,
    scene_id: int,
    start_image_prompt: str | None = None,
    video_prompt: str | None = None,
) -> None:
    scenes = load_scene_list(project_dir)
    scene = find_scene(scenes, scene_id)
    if start_image_prompt is not None:
        scene["start_image_prompt"] = start_image_prompt.strip()
    if video_prompt is not None:
        scene["video_prompt"] = video_prompt.strip()
    save_scene_list(project_dir, scenes)
