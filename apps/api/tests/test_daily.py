from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.daily.router import views_per_day
from app.main import create_app
from app.references.models import ReferenceCandidate


def candidate(video_id: str, views: int, days_ago: int) -> ReferenceCandidate:
    uploaded = (date.today() - timedelta(days=days_ago)).isoformat() + "T00:00:00Z"
    return ReferenceCandidate(
        video_id=video_id, url=f"https://youtube.com/shorts/{video_id}", title=video_id, channel_id="c",
        channel_name="채널", thumbnail_url="https://x/t.jpg", upload_date=uploaded, duration_seconds=30,
        view_count=views, subscriber_count=1000, source_type="search",
    )


class FakeYouTube:
    calls = 0

    def __init__(self, api_key: str):
        pass

    def search(self, request):
        FakeYouTube.calls += 1
        return [candidate("old_big", 700_000, 7), candidate("new_fast", 300_000, 1)]


def test_views_per_day_handles_bad_dates():
    assert views_per_day(1000, "not-a-date", date.today()) == 1000


def test_daily_refresh_ranks_by_views_per_day_and_caches_for_the_day(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path, youtube_client_factory=FakeYouTube))
    assert client.post("/api/daily-references/refresh").status_code == 400  # no keywords yet

    client.put("/api/daily-references/keywords", json={"keywords": ["돈 습관", "money habits", "돈 습관"]})
    first = client.post("/api/daily-references/refresh").json()
    again = client.post("/api/daily-references/refresh").json()

    assert first["keywords"] == ["돈 습관", "money habits"]
    assert [i["video_id"] for i in first["items"]] == ["new_fast", "old_big"]  # 300k/1d beats 700k/7d
    assert FakeYouTube.calls == 2 and again == first  # second refresh served from today's cache
