"""Member check for every request that changes something. The web app sends its Supabase login token;
we ask Supabase who it is and read that person's row in shorts_members (RLS lets a user read only their own).
With no Supabase URL configured the check is off, like the login screen."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable

import httpx
from fastapi import HTTPException, Request

from app.core.settings import AppSettings

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}  # <img>/<audio> tags can't send a token, so reads stay open
CACHE_SECONDS = 60


def lookup_member(settings: AppSettings, token: str) -> dict | None:
    """The caller's shorts_members row, or None when the token is bad or they have no row."""
    base, key = settings.vite_supabase_url.rstrip("/"), settings.vite_supabase_publishable_key
    headers = {"apikey": key, "Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=10) as http:
        who = http.get(f"{base}/auth/v1/user", headers=headers)
        if who.status_code != 200:
            return None
        rows = http.get(f"{base}/rest/v1/shorts_members", headers=headers,
                        params={"select": "plan,until,daily_limit", "user_id": f"eq.{who.json()['id']}"})
        rows.raise_for_status()
    return (rows.json() or [None])[0]


def is_active(member: dict | None) -> bool:
    if member is None:
        return False
    until = member.get("until")
    return until is None or datetime.fromisoformat(until.replace("Z", "+00:00")) > datetime.now(timezone.utc)


def create_member_guard(settings_provider: Callable[[], AppSettings], lookup=lookup_member):
    cache: dict[str, tuple[float, bool]] = {}  # token -> (checked at, allowed)

    def guard(request: Request) -> None:
        settings = settings_provider()
        if not settings.vite_supabase_url or request.method in SAFE_METHODS:
            return
        auth = request.headers.get("authorization", "")
        token = auth[7:] if auth.lower().startswith("bearer ") else ""
        if not token:
            raise HTTPException(401, "로그인이 필요합니다.")
        hit = cache.get(token)
        if hit is None or time.monotonic() - hit[0] > CACHE_SECONDS:
            try:
                allowed = is_active(lookup(settings, token))
            except httpx.HTTPError:
                raise HTTPException(503, "회원 확인 서버에 연결하지 못했어요. 잠시 뒤에 다시 해 주세요.")
            hit = cache[token] = (time.monotonic(), allowed)
        if not hit[1]:
            raise HTTPException(403, "쇼츠공방 회원이 아니거나 이용 기간이 끝났어요.")

    return guard
