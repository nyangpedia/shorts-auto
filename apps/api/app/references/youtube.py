"""YouTube Data API: find reference Shorts and fill in their stats.

Quota (10,000 units/day free): search.list costs 100 per call, videos/channels/playlistItems cost 1.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

import httpx

from app.references.models import ReferenceCandidate, ReferenceSearchRequest

API = "https://www.googleapis.com/youtube/v3"
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,32}$")
_ISO_DURATION = re.compile(r"^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")
BATCH = 50  # most ids the videos/channels endpoints accept per call
WINDOW_DAYS = 7  # a long date range is searched week by week so recent weeks aren't crowded out
MAX_KEYWORDS = 9


# ── parsing ─────────────────────────────────────────────────────────────────

def extract_youtube_video_id(url: str) -> str:
    link = urlparse(url.strip())
    host = link.netloc.lower()
    if host not in YOUTUBE_HOSTS:
        raise ValueError("Only YouTube URLs are supported")
    if host == "youtu.be":
        video_id = link.path.strip("/").split("/")[0]
    elif link.path == "/watch":
        video_id = parse_qs(link.query).get("v", [""])[0]
    elif link.path.startswith("/shorts/"):
        video_id = link.path.split("/")[2]
    else:
        video_id = ""
    if not VIDEO_ID_RE.fullmatch(video_id):
        raise ValueError("Could not extract a valid YouTube video ID")
    return video_id


def parse_iso8601_duration_seconds(value: str) -> int:
    """"PT1M5S" → 65."""
    match = _ISO_DURATION.fullmatch(value)
    if not match:
        raise ValueError(f"Unsupported YouTube duration: {value}")
    days, hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return ((days * 24 + hours) * 60 + minutes) * 60 + seconds


def extract_youtube_channel_identifier(query: str) -> tuple[str, str]:
    """("id" | "handle" | "query", value) from a channel URL, @handle, UC… id, or free text."""
    text = query.strip()
    link = urlparse(text)
    if link.netloc.lower() in YOUTUBE_HOSTS:
        path = link.path.strip("/")
        head, _, rest = path.partition("/")
        if path.startswith("@"):
            return "handle", path
        if head == "channel" and rest:
            return "id", rest.split("/")[0]
        if head in ("c", "user") and rest:
            return "query", rest.split("/")[0]
        if path:
            return "query", path
    if text.startswith("@"):
        return "handle", text
    if text.startswith("UC") and len(text) == 24:
        return "id", text
    return "query", text


def sort_by_vs_ratio(candidates: list[ReferenceCandidate]) -> list[ReferenceCandidate]:
    """Biggest views-per-subscriber first; videos without subscriber counts go last."""
    return sorted(candidates, key=lambda c: (c.vs_ratio is not None, c.vs_ratio or 0, c.view_count), reverse=True)


def _batches(items: list, size: int = BATCH):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _as_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def date_windows(request: ReferenceSearchRequest) -> list[tuple[str | None, str | None]]:
    """The requested range cut into consecutive 7-day windows (oldest first), or the range as given."""
    first, last = _as_date(request.published_after), _as_date(request.published_before)
    if first is None or last is None or first > last:
        return [(request.published_after, request.published_before)]
    windows = []
    end = last
    while end >= first:
        start = max(first, end - timedelta(days=WINDOW_DAYS - 1))
        windows.append((start.isoformat(), end.isoformat()))
        end = start - timedelta(days=1)
    return windows[::-1]


# ── language filter (references must be readable to pick from) ─────────────

REFERENCE_LANGUAGES = ("ko", "en", "ja", "zh")
# Indic scripts (Devanagari … Sinhala), Arabic, Thai — titles the user can't read to pick a reference.
_UNREADABLE_SCRIPTS = re.compile("[ऀ-෿؀-ۿ฀-๿]")
EXCLUDED_CHANNEL_COUNTRIES = ("IN", "PK", "BD")


def is_readable_language(snippet: dict) -> bool:
    """Search results only: keep ko/en/ja/zh. Many videos don't declare a language, so the title script is the fallback."""
    declared = (snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage") or "").split("-")[0].lower()
    if declared and declared not in REFERENCE_LANGUAGES and declared not in ("und", "zxx"):
        return False
    return not _UNREADABLE_SCRIPTS.search(snippet.get("title", ""))


def is_readable_channel(channel_snippet: dict) -> bool:
    """Some channels label videos "en" with English titles but narrate in Telugu/Hindi; the channel gives it away."""
    if channel_snippet.get("country") in EXCLUDED_CHANNEL_COUNTRIES:
        return False
    return not _UNREADABLE_SCRIPTS.search(channel_snippet.get("description", ""))


# ── client ──────────────────────────────────────────────────────────────────

class YouTubeClient:
    def __init__(self, api_key: str, http_client: httpx.Client | None = None):
        if not api_key:
            raise ValueError("YouTube API key is missing")
        self.api_key = api_key
        self.http_client = http_client or httpx.Client(timeout=20)

    def _get(self, endpoint: str, **params) -> dict:
        response = self.http_client.get(f"{API}/{endpoint}", params={**params, "key": self.api_key})
        response.raise_for_status()
        return response.json()

    def _try_get(self, endpoint: str, **params) -> list[dict]:
        """Items, or [] when the lookup fails — used while resolving a channel by several routes."""
        response = self.http_client.get(f"{API}/{endpoint}", params={**params, "key": self.api_key})
        return response.json().get("items", []) if response.status_code == 200 else []

    def resolve_channel(self, channel_query: str) -> tuple[str, str]:
        """(channel id, uploads playlist id) for a channel URL, @handle, id, or name."""
        kind, value = extract_youtube_channel_identifier(channel_query)
        found: list[dict] = []
        if kind == "id":
            found = self._try_get("channels", part="contentDetails", id=value)
        elif kind == "handle":
            found = self._try_get("channels", part="contentDetails", forHandle=value if value.startswith("@") else f"@{value}")
        if not found:
            hits = self._try_get("search", part="snippet", type="channel", q=value.lstrip("@"), maxResults=1)
            hit_id = hits and (hits[0].get("id", {}).get("channelId") or hits[0].get("snippet", {}).get("channelId"))
            if hit_id:
                found = self._try_get("channels", part="contentDetails", id=hit_id) or [{"id": hit_id}]
        if not found:
            raise ValueError(f"유튜브 채널을 찾을 수 없습니다: {channel_query}")
        channel_id = found[0]["id"]
        uploads = found[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", "")
        if not uploads and channel_id.startswith("UC"):
            uploads = "UU" + channel_id[2:]  # every channel's uploads playlist id mirrors its channel id
        return channel_id, uploads

    def search(self, request: ReferenceSearchRequest) -> list[ReferenceCandidate]:
        channel_id, uploads = self.resolve_channel(request.channel_query) if request.channel_query else ("", "")
        if request.keyword:
            return self._search_keywords(request, channel_id)
        if uploads:
            return self._hydrate(self._latest_uploads(uploads, request.max_results), "search", request)[: request.max_results]
        return []

    def _search_keywords(self, request: ReferenceSearchRequest, channel_id: str) -> list[ReferenceCandidate]:
        # Comma-separated keywords = one search each: YouTube answers in the query's language, so foreign
        # references need foreign keywords. A call costs 100 units whatever maxResults is, so take 50.
        keywords = [k.strip() for k in request.keyword.split(",") if k.strip()][:MAX_KEYWORDS]
        params = {"part": "snippet", "type": "video", "maxResults": 50}
        if request.duration_filter in ("under_60", "under_120", "under_180"):
            params["videoDuration"] = "short"  # YouTube's "short" = under 4 min; skips long videos we'd drop anyway
        if channel_id:
            params["channelId"] = channel_id
        ids: list[str] = []
        for keyword in keywords:
            for after, before in date_windows(request):
                window = {}
                if after:
                    window["publishedAfter"] = f"{after}T00:00:00Z"
                if before:
                    window["publishedBefore"] = f"{before}T23:59:59Z"
                for item in self._get("search", **params, **window, q=keyword).get("items", []):
                    video_id = item.get("id", {}).get("videoId")
                    if video_id and video_id not in ids:
                        ids.append(video_id)
        return self._hydrate(ids, "search", request)[: request.max_results * len(keywords)]

    def _latest_uploads(self, playlist_id: str, wanted: int) -> list[str]:
        limit = min(200, max(50, wanted * 4))  # extra, because duration/view filters drop many
        ids: list[str] = []
        page = None
        while len(ids) < limit:
            extra = {"pageToken": page} if page else {}
            data = self._get("playlistItems", part="contentDetails", playlistId=playlist_id,
                             maxResults=min(50, limit - len(ids)), **extra)
            items = data.get("items", [])
            for item in items:
                video_id = item.get("contentDetails", {}).get("videoId")
                if video_id and video_id not in ids:
                    ids.append(video_id)
            page = data.get("nextPageToken")
            if not items or not page:
                break
        return ids

    def get_direct(self, url: str) -> ReferenceCandidate:
        found = self._hydrate([extract_youtube_video_id(url)], "direct", None)
        if not found:
            raise ValueError("YouTube video not found or unavailable")
        return found[0]

    def _hydrate(self, video_ids: list[str], source_type: str, request: ReferenceSearchRequest | None) -> list[ReferenceCandidate]:
        """Fetch stats for the ids (with their channels) and apply the request's filters."""
        results: list[ReferenceCandidate] = []
        for batch in _batches(video_ids):
            videos = {v["id"]: v for v in self._get("videos", part="snippet,contentDetails,statistics", id=",".join(batch)).get("items", [])}
            channel_ids = sorted({v["snippet"]["channelId"] for v in videos.values() if "snippet" in v})
            channels: dict[str, dict] = {}
            for channel_batch in _batches(channel_ids):
                # snippet costs no extra quota here and carries country/description for the language filter
                for ch in self._get("channels", part="snippet,statistics", id=",".join(channel_batch)).get("items", []):
                    channels[ch["id"]] = ch
            for video_id in batch:
                candidate = self._to_candidate(video_id, videos.get(video_id), channels, source_type, request)
                if candidate:
                    results.append(candidate)
        return sort_by_vs_ratio(results)

    @staticmethod
    def _to_candidate(video_id, video, channels, source_type, request) -> ReferenceCandidate | None:
        snippet = (video or {}).get("snippet")
        duration = (video or {}).get("contentDetails", {}).get("duration")
        if not snippet or not duration:
            return None
        try:
            seconds = parse_iso8601_duration_seconds(duration)
        except ValueError:
            return None
        channel = channels.get(snippet["channelId"], {})
        views = int(video.get("statistics", {}).get("viewCount", 0))
        subs_raw = channel.get("statistics", {}).get("subscriberCount")
        subscribers = int(subs_raw) if subs_raw is not None else None
        uploaded = snippet["publishedAt"][:10]
        if request is not None:
            too_many_subs = request.maximum_subscribers is not None and (subscribers is None or subscribers > request.maximum_subscribers)
            outside_dates = (request.published_after and uploaded < request.published_after) or (
                request.published_before and uploaded > request.published_before)
            unreadable = not (is_readable_language(snippet) and is_readable_channel(channel.get("snippet", {})))
            if not request.matches_duration(seconds) or unreadable or views < request.minimum_views or too_many_subs or outside_dates:
                return None
        thumbs = snippet.get("thumbnails", {})
        return ReferenceCandidate(
            video_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
            title=snippet["title"],
            channel_id=snippet["channelId"],
            channel_name=snippet["channelTitle"],
            thumbnail_url=thumbs.get("high", {}).get("url") or thumbs.get("default", {}).get("url", ""),
            upload_date=snippet["publishedAt"],
            duration_seconds=seconds,
            view_count=views,
            subscriber_count=subscribers,
            source_type=source_type,
        )
