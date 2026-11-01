"""The topics a user has already made, kept in their Supabase account so every PC sees the same list.
Rows are the caller's own (RLS on shorts_topic_log), reached with the caller's login token."""
from __future__ import annotations

import httpx

from app.core.settings import AppSettings


def sync_used(settings: AppSettings, token: str, rows: list[dict]) -> list[dict]:
    """Upsert this PC's used topics, then return every used topic the account has, newest first."""
    url = f"{settings.vite_supabase_url.rstrip('/')}/rest/v1/shorts_topic_log"
    headers = {"apikey": settings.vite_supabase_publishable_key, "Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=10) as http:
        if rows:  # user_id fills itself from the token (column default auth.uid())
            http.post(url, headers={**headers, "Prefer": "resolution=merge-duplicates"},
                      params={"on_conflict": "user_id,topic_id"}, json=rows).raise_for_status()
        listed = http.get(url, headers=headers, params={"select": "topic_id,title,project_id,updated_at", "order": "updated_at.desc"})
        listed.raise_for_status()
    return listed.json()
