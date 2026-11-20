"""What this account has made, kept in Supabase so every PC can see it (the files stay on each PC).
Rows are the caller's own (RLS on shorts_project_log), reached with the caller's login token."""
from __future__ import annotations

import platform

import httpx

from app.core.settings import AppSettings
from app.projects.models import Project

STEP_KO = {"Reference": "레퍼런스", "STT": "분석", "Analysis": "분석", "Candidates": "대본", "Script": "대본", "Production": "제작", "Render": "완성"}
COLUMNS = "project_id,title,step,rendered,uploaded,archived,device,updated_at"


def device_name() -> str:
    return platform.node() or "이 PC"


def project_row(project: Project, device: str) -> dict:
    rendered = bool(project.generated_files.get("final_video"))
    return {
        "project_id": project.project_id,
        "title": project.display_name if project.project_title == "untitled" else project.project_title,
        "step": "완성" if rendered else STEP_KO.get(project.current_step, project.current_step),
        "rendered": rendered,
        "uploaded": bool(project.generated_files.get("youtube_video")),
        "archived": project.archived,
        "device": device,
        "updated_at": project.updated_at,
    }


def sync_projects(settings: AppSettings, token: str, rows: list[dict]) -> list[dict]:
    """Upsert this PC's projects, then return every project the account has made on any PC, newest first."""
    url = f"{settings.vite_supabase_url.rstrip('/')}/rest/v1/shorts_project_log"
    headers = {"apikey": settings.vite_supabase_publishable_key, "Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=10) as http:
        if rows:  # user_id fills itself from the token (column default auth.uid())
            http.post(url, headers={**headers, "Prefer": "resolution=merge-duplicates"},
                      params={"on_conflict": "user_id,device,project_id"}, json=rows).raise_for_status()
        listed = http.get(url, headers=headers, params={"select": COLUMNS, "order": "updated_at.desc"})
        listed.raise_for_status()
    return listed.json()
