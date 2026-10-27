"""오늘의 레퍼런스: one cached search per day over saved niche keywords (last 7 days, shorts)."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.settings import AppSettings
from app.projects.service import list_projects
from app.references.files import SELECTED_REFERENCE_FILE
from app.references.models import ReferenceSearchRequest

DAILY_FILE = "_daily_references.json"
MAX_KEYWORDS = 8
KEEP = 60


class KeywordsRequest(BaseModel):
    keywords: list[str] = Field(max_length=MAX_KEYWORDS)

    @field_validator("keywords")
    @classmethod
    def clean(cls, value: list[str]) -> list[str]:
        cleaned = [k.strip()[:50] for k in value if k.strip()]
        return list(dict.fromkeys(cleaned))


def _load(outputs: Path) -> dict:
    try:
        return json.loads((outputs / DAILY_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"keywords": [], "fetched_on": None, "items": []}


def _save(outputs: Path, data: dict) -> None:
    (outputs / DAILY_FILE).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _used_videos(outputs: Path) -> dict[str, str]:
    used = {}
    for project in list_projects(outputs):
        try:
            ref = json.loads((outputs / project.project_id / SELECTED_REFERENCE_FILE).read_text(encoding="utf-8"))
            used[ref["video_id"]] = project.project_id
        except (OSError, ValueError, KeyError):
            continue
    return used


def views_per_day(view_count: int, upload_date: str, today: date) -> int:
    try:
        uploaded = datetime.fromisoformat(upload_date.replace("Z", "+00:00")).date()
    except ValueError:
        return view_count
    return view_count // max(1, (today - uploaded).days)


def _response(outputs: Path, data: dict) -> dict:
    used = _used_videos(outputs)
    items = [{**item, "used_by": used.get(item["video_id"])} for item in data.get("items", [])]
    return {"keywords": data.get("keywords", []), "fetched_on": data.get("fetched_on"), "items": items}


def create_daily_router(
    outputs_dir_provider: Callable[[], Path],
    settings_provider: Callable[[], AppSettings],
    youtube_client_factory: Callable[[str], object],
) -> APIRouter:
    router = APIRouter(prefix="/api/daily-references", tags=["daily"])

    @router.get("")
    def get_daily(outputs: Path = Depends(outputs_dir_provider)):
        return _response(outputs, _load(outputs))

    @router.put("/keywords")
    def set_keywords(payload: KeywordsRequest, outputs: Path = Depends(outputs_dir_provider)):
        data = _load(outputs)
        if data.get("keywords") != payload.keywords:
            data = {"keywords": payload.keywords, "fetched_on": None, "items": []}  # stale results for old keywords
            _save(outputs, data)
        return _response(outputs, data)

    @router.post("/refresh")
    def refresh(
        force: bool = False,
        outputs: Path = Depends(outputs_dir_provider),
        settings: AppSettings = Depends(settings_provider),
    ):
        data = _load(outputs)
        today = date.today()
        if not data.get("keywords"):
            raise HTTPException(status_code=400, detail="분야 키워드를 먼저 저장하세요.")
        if data.get("fetched_on") == today.isoformat() and not force:
            return _response(outputs, data)  # one search per day protects the YouTube quota
        try:
            client = youtube_client_factory(settings.youtube_api_key)
            found: dict[str, dict] = {}
            for keyword in data["keywords"]:
                request = ReferenceSearchRequest(
                    keyword=keyword,
                    published_after=(today - timedelta(days=7)).isoformat(),
                    published_before=today.isoformat(),
                    duration_filter="under_180",
                    max_results=50,
                )
                for candidate in client.search(request):
                    item = candidate.model_dump()
                    item["keyword"] = keyword
                    item["views_per_day"] = views_per_day(candidate.view_count, candidate.upload_date, today)
                    found.setdefault(candidate.video_id, item)
        except (ValueError, httpx.HTTPError) as exc:
            raise HTTPException(status_code=400, detail=f"YouTube 검색 실패: {exc}") from exc
        items = sorted(found.values(), key=lambda i: i["views_per_day"], reverse=True)[:KEEP]
        data = {"keywords": data["keywords"], "fetched_on": today.isoformat(), "items": items}
        _save(outputs, data)
        return _response(outputs, data)

    return router
