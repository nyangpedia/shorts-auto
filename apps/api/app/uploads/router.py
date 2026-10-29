"""YouTube upload for the user's own channel.

Each install uses its own Google Cloud OAuth client (client_secret.json at the repo root) and
stores its own refresh token, so no shared app review is needed. Videos always go up private;
the user publishes from Studio after the pre-upload checklist.
"""
from __future__ import annotations

import json
import re
import secrets
import shutil
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.projects.service import read_project, save_project

CLIENT_SECRET_FILE = "client_secret.json"
TOKEN_FILE = ".youtube_token.json"
# Upload, plus read-only channel stats/analytics for the "why didn't it work" review (asked once, at connect).
SCOPE = " ".join([
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
])
REDIRECT_URI = "http://127.0.0.1:8000/api/youtube/callback"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
THUMBNAIL_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"


class ClientSecretRequest(BaseModel):
    content: str = Field(max_length=20_000)


class UploadFilesRequest(BaseModel):
    title: str = Field(default="", max_length=100)


def safe_filename(title: str) -> str:
    """A title as a Windows/macOS-safe file name (YouTube suggests the file name as the video title)."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title).strip().rstrip(".")
    return name[:80] or "shorts"


def open_folder(folder: Path) -> None:
    """Show the folder in the file manager of the PC running the app (the API only listens on 127.0.0.1)."""
    import os
    import subprocess
    import sys

    if sys.platform == "win32":
        os.startfile(folder)  # noqa: S606 - a local folder we just wrote
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])


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

    @router.put("/api/youtube/client-secret")
    def save_client_secret(payload: ClientSecretRequest):
        try:
            data = json.loads(payload.content)
            cfg = data.get("installed") or data.get("web") or {}
            assert all(cfg.get(k) for k in ("client_id", "client_secret", "auth_uri", "token_uri"))
        except (ValueError, AttributeError, AssertionError) as exc:
            raise HTTPException(status_code=400, detail="구글 클라우드에서 받은 OAuth 클라이언트 JSON 파일이 아닙니다.") from exc
        if "installed" not in data:
            raise HTTPException(status_code=400, detail="'데스크톱 앱' 유형으로 만든 OAuth 클라이언트가 필요합니다.")
        (repo_root / CLIENT_SECRET_FILE).write_text(json.dumps(data), encoding="utf-8")
        (repo_root / TOKEN_FILE).unlink(missing_ok=True)  # a new client invalidates the old login
        return status()

    @router.delete("/api/youtube/connection")
    def disconnect():
        (repo_root / TOKEN_FILE).unlink(missing_ok=True)
        return status()

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

    @router.post("/api/projects/{project_id}/upload-files")
    def upload_files(project_id: str, payload: UploadFilesRequest, outputs: Path = Depends(outputs_dir_provider)):
        """Uploading by hand in YouTube Studio: the video (and thumbnail) copied under the title, folder opened.
        API uploads from an unaudited Google project stay locked private, so this is the default path."""
        try:
            project = read_project(outputs, project_id)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        source = outputs / project_id
        if not (source / "final.mp4").exists():
            raise HTTPException(status_code=400, detail="final.mp4 영상이 아직 없습니다. 먼저 렌더링하세요.")
        folder = source / "업로드"
        shutil.rmtree(folder, ignore_errors=True)  # only this export's copies live here
        folder.mkdir()
        name = safe_filename(payload.title or project.project_title)
        files = [f"{name}.mp4"]
        shutil.copyfile(source / "final.mp4", folder / files[0])
        if (source / "thumbnail.jpg").exists():
            files.append(f"{name}_썸네일.jpg")
            shutil.copyfile(source / "thumbnail.jpg", folder / files[1])
        open_folder(folder)
        return {"folder": str(folder), "files": files}

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
        thumbnail_note = None
        thumbnail = outputs / project_id / "thumbnail.jpg"
        if thumbnail.exists():
            # Best effort: custom thumbnails need a phone-verified channel, and the video itself is already up.
            with httpx.Client(transport=transport, timeout=120) as http:
                sent = http.post(THUMBNAIL_URL, params={"videoId": video_id}, content=thumbnail.read_bytes(),
                                 headers={**auth, "Content-Type": "image/jpeg"})
            if sent.status_code != 200:
                thumbnail_note = "영상은 올라갔지만 썸네일은 적용되지 않았습니다. 채널 전화번호 인증이 필요할 수 있어요. 스튜디오에서 직접 올려주세요."
        project = read_project(outputs, project_id)
        project.generated_files["youtube_video"] = video_id
        save_project(outputs, project)
        return {"video_id": video_id, "url": f"https://youtu.be/{video_id}", "studio_url": f"https://studio.youtube.com/video/{video_id}/edit",
                "thumbnail_note": thumbnail_note}

    return router
