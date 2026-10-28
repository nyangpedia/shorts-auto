"""주제 창고: every reference analysis suggests 5 topics; this collects them across projects
so one analysed reference can feed several days of videos."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.projects.router import MAX_PROJECT_ID_ATTEMPTS, timestamp_id
from app.projects.service import create_project, list_projects, read_project, save_project
from app.references.files import (
    REFERENCE_ANALYSIS_FILE,
    REFERENCE_ANALYSIS_MARKDOWN_FILE,
    REFERENCE_SCRIPT_FILE,
    SELECTED_REFERENCE_FILE,
)

USED_TOPICS_FILE = "_topics_used.json"
HIDDEN_TOPICS_FILE = "_topics_hidden.json"  # topics removed from the 창고; analyses stay untouched
COPIED_FILES = [REFERENCE_SCRIPT_FILE, REFERENCE_ANALYSIS_FILE, REFERENCE_ANALYSIS_MARKDOWN_FILE, SELECTED_REFERENCE_FILE]


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def collect_topics(outputs: Path) -> list[dict]:
    used = _read_json(outputs / USED_TOPICS_FILE)
    hidden = set(_read_json(outputs / HIDDEN_TOPICS_FILE).get("ids", []))
    topics = []
    for project in list_projects(outputs):
        analysis_path = outputs / project.project_id / REFERENCE_ANALYSIS_FILE
        if not analysis_path.exists() or "topic_source" in project.generated_files:
            continue  # projects started from a topic carry a copy of the source analysis
        analysis = _read_json(analysis_path)
        reference = _read_json(outputs / project.project_id / SELECTED_REFERENCE_FILE)
        created = datetime.fromtimestamp(analysis_path.stat().st_mtime).isoformat(timespec="minutes")
        for index, topic in enumerate(analysis.get("recommended_topics") or []):
            topic_id = f"{project.project_id}:{index}"
            if topic_id in hidden:
                continue
            topics.append({
                "id": topic_id,
                "source_project_id": project.project_id,
                "reference_title": reference.get("title") or project.project_title,
                "title": topic.get("title", ""),
                "hook": topic.get("hook", ""),
                "category": topic.get("category", ""),
                "formula": topic.get("formula", ""),
                "analyzed_at": created,
                "used_by": used.get(topic_id),
            })
    unused =sorted((t for t in topics if not t["used_by"]), key=lambda t: t["analyzed_at"], reverse=True)
    return unused + [t for t in topics if t["used_by"]]


class HideTopicsRequest(BaseModel):
    ids: list[str]


def create_topics_router(outputs_dir_provider: Callable[[], Path]) -> APIRouter:
    router = APIRouter(prefix="/api/topics", tags=["topics"])

    @router.get("")
    def get_topics(outputs: Path = Depends(outputs_dir_provider)):
        return {"topics": collect_topics(outputs)}

    @router.post("/hide")
    def hide_topics(payload: HideTopicsRequest, outputs: Path = Depends(outputs_dir_provider)):
        path = outputs / HIDDEN_TOPICS_FILE
        hidden = set(_read_json(path).get("ids", [])) | set(payload.ids)
        path.write_text(json.dumps({"ids": sorted(hidden)}, ensure_ascii=False), encoding="utf-8")
        return {"topics": collect_topics(outputs)}

    @router.post("/{source_project_id}/{index}/start")
    def start_from_topic(source_project_id: str, index: int, outputs: Path = Depends(outputs_dir_provider)):
        topic_id = f"{source_project_id}:{index}"
        topic = next((t for t in collect_topics(outputs) if t["id"] == topic_id), None)
        if topic is None:
            raise HTTPException(status_code=404, detail="주제를 찾을 수 없습니다.")
        try:
            read_project(outputs, source_project_id)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="원본 프로젝트가 없습니다.") from exc

        project = None
        for offset in range(MAX_PROJECT_ID_ATTEMPTS):
            try:
                project = create_project(outputs, topic["title"][:80] or "untitled", timestamp_id(offset))
                break
            except FileExistsError:
                continue
        if project is None:
            raise HTTPException(status_code=409, detail="Could not allocate a unique project_id")

        source, target = outputs / source_project_id, outputs / project.project_id
        for name in COPIED_FILES:
            if (source / name).exists():
                shutil.copyfile(source / name, target / name)
        project.current_step = "Candidates"
        project.generated_files.update({
            "reference_script": REFERENCE_SCRIPT_FILE,
            "reference_analysis": REFERENCE_ANALYSIS_FILE,
            "topic_source": topic_id,
        })
        save_project(outputs, project)

        used = _read_json(outputs / USED_TOPICS_FILE)
        used[topic_id] = project.project_id
        (outputs / USED_TOPICS_FILE).write_text(json.dumps(used, ensure_ascii=False), encoding="utf-8")
        return {"project": read_project(outputs, project.project_id).model_dump(), "feedback": f"{index + 1}번 추천 주제로 작성: {topic['title']}"}

    return router
