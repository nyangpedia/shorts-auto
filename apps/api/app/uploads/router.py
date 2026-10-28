"""YouTube upload for the user's own channel.

Each install uses its own Google Cloud OAuth client (client_secret.json at the repo root) and
stores its own refresh token, so no shared app review is needed. Videos always go up private;
the user publishes from Studio after the pre-upload checklist.
"""
from __future__ import annotations

import json
import re
import secrets
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.projects.service import read_project, save_project

CLIENT_SECRET_FILE = "client_secret.json"
TOKEN_FILE = ".youtube_token.json"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"
REDIRECT_URI = "http://127.0.0.1:8000/api/youtube/callback"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


class UploadRequest(BaseModel):
    title: str
    description: str = ""
    tags: str = ""


def parse_tags(raw: str) -> list[str]:
    """'#a #b, c' -> ['a', 'b', 'c']; YouTube caps the combined tag text, so keep the first 15."""
    return [t for t in re.split(r"[\s,]+", raw.replace("#", " ")) if t][:15]


def create_uploads_router(
    repo_root: Path,
    outputs_dir_provider: Callable[[], Path],
    transport: httpx.BaseTransport | None = None,
) -> APIRouter:
    router = APIRouter(tags=["youtube-upload"])
    pending_states: set[str] = set()

    def client_config() -> dict:
        path = repo_root / CLIENT_SECRET_FILE
        if not path.exists():
            raise HTTPException(status_code=400, detail="client_secret.json 이 프로젝트 폴더에 없습니다.")
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("installed") or data.get("web") or {}

    def refresh_token() -> str | None:
        try:
            return json.loads((repo_root / TOKEN_FILE).read_text(encoding="utf-8")).get("refresh_token")
        except (OSError, ValueError):
            return None

    def token_request(cfg: dict, **form: str) -> dict:
        with httpx.Client(transport=transport, timeout=30) as http:
            response = http.post(cfg["token_uri"], data={"client_id": cfg["client_id"], "client_secret": cfg["client_secret"], **form})
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"구글 로그인 실패: {response.text[:200]}")
        return response.json()

    @router.get("/api/youtube/status")
    def status():
        return {"configured": (repo_root / CLIENT_SECRET_FILE).exists(), "connected": refresh_token() is not None}

    @router.get("/api/youtube/connect")
    def connect():
        cfg = client_config()
        state = secrets.token_urlsafe(16)
        pending_states.add(state)
        query = urlencode({
            "client_id": cfg["client_id"], "redirect_uri": REDIRECT_URI, "response_type": "code",
            "scope": SCOPE, "access_type": "offline", "prompt": "consent", "state": state,
        })
        return {"auth_url": f"{cfg['auth_uri']}?{query}"}

    @router.get("/api/youtube/callback", response_class=HTMLResponse)
    def callback(code: str = "", state: str = "", error: str = ""):
        if error or state not in pending_states:
            return HTMLResponse("<h3>연결하지 못했습니다. 앱에서 다시 시도하세요.</h3>", status_code=400)
        pending_states.discard(state)
        tokens = token_request(client_config(), code=code, redirect_uri=REDIRECT_URI, grant_type="authorization_code")
        if not tokens.get("refresh_token"):
            return HTMLResponse("<h3>refresh token 을 받지 못했습니다. 구글 계정의 앱 권한을 지우고 다시 연결하세요.</h3>", status_code=400)
        (repo_root / TOKEN_FILE).write_text(json.dumps({"refresh_token": tokens["refresh_token"]}), encoding="utf-8")
        return HTMLResponse("<h3>연결됐습니다. 이 창을 닫고 쇼츠공방으로 돌아가세요.</h3>")

    @router.post("/api/projects/{project_id}/youtube/upload")
    def upload(project_id: str, payload: UploadRequest, outputs: Path = Depends(outputs_dir_provider)):
        try:
            read_project(outputs, project_id)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        video = outputs / project_id / "final.mp4"
        if not video.exists():
            raise HTTPException(status_code=400, detail="final.mp4 영상이 아직 없습니다. 먼저 렌더링하세요.")
        token = refresh_token()
        if not token:
            raise HTTPException(status_code=400, detail="유튜브 계정이 연결되지 않았습니다.")
        if not payload.title.strip():
            raise HTTPException(status_code=400, detail="제목을 입력하세요.")

        access = token_request(client_config(), refresh_token=token, grant_type="refresh_token")["access_token"]
        description = payload.description.strip()
        if "#shorts" not in description.lower():
            description = f"{description}\n\n#Shorts".strip()
        metadata = {
            "snippet": {"title": payload.title.strip()[:100], "description": description, "tags": parse_tags(payload.tags), "categoryId": "22"},
            "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
        }
        size = video.stat().st_size
        auth = {"Authorization": f"Bearer {access}"}
        with httpx.Client(transport=transport, timeout=600) as http:
            start = http.post(
                UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"}, json=metadata,
                headers={**auth, "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
            )
            if start.status_code != 200:
                raise HTTPException(status_code=400, detail=f"업로드 시작 실패: {start.text[:300]}")
            done = http.put(start.headers["location"], content=video.read_bytes(), headers={**auth, "Content-Type": "video/mp4"})
        if done.status_code not in (200, 201):
            raise HTTPException(status_code=400, detail=f"업로드 실패: {done.text[:300]}")

        video_id = done.json()["id"]
        project = read_project(outputs, project_id)
        project.generated_files["youtube_video"] = video_id
        save_project(outputs, project)
        return {"video_id": video_id, "url": f"https://youtu.be/{video_id}", "studio_url": f"https://studio.youtube.com/video/{video_id}/edit"}

    return router
