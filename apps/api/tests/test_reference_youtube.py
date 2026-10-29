"""YouTube client against a fake Data API: URL parsing, search, hydration and filters."""
import httpx
import pytest

from app.references.models import ReferenceCandidate, ReferenceSearchRequest
from app.references.youtube import (
    YouTubeClient,
    date_windows,
    extract_youtube_channel_identifier,
    extract_youtube_video_id,
    is_readable_channel,
    is_readable_language,
    parse_iso8601_duration_seconds,
    sort_by_vs_ratio,
)

CHANNEL = "UC1234567890123456789012"
UPLOADS = "UU1234567890123456789012"


def snippet(title: str, channel: str = "channel-1", published: str = "2026-10-01T00:00:00Z") -> dict:
    return {"title": title, "channelId": channel, "channelTitle": "채널", "publishedAt": published,
            "thumbnails": {"high": {"url": "https://example.com/t.jpg"}}}


def vid(video_id: str, title: str = "검색 결과", duration: str = "PT45S", views: int = 120000, **snip) -> dict:
    return {"id": video_id, "snippet": snippet(title, **snip), "contentDetails": {"duration": duration},
            "statistics": {"viewCount": str(views)}}


class FakeAPI(httpx.BaseTransport):
    """Answers /search with `found(params)` ids and /videos, /channels from fixed tables. Records every call."""

    def __init__(self, videos: list[dict] = (), subscribers: dict[str, int] | None = None, found=None, uploads=None):
        self.videos = list(videos)
        self.subscribers = subscribers or {"channel-1": 3000}
        self.found = found or (lambda params: [v["id"] for v in self.videos])
        self.uploads = uploads or []
        self.calls: list[tuple[str, dict]] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        endpoint, params = request.url.path.rsplit("/", 1)[-1], dict(request.url.params)
        self.calls.append((endpoint, params))
        if endpoint == "search":
            items = [{"id": {"videoId": i}} for i in self.found(params)]
        elif endpoint == "videos":
            items = self.videos
        elif endpoint == "channels":
            items = [{"id": cid, "statistics": {"subscriberCount": str(n)},
                      "contentDetails": {"relatedPlaylists": {"uploads": UPLOADS}}} for cid, n in self.subscribers.items()]
        elif endpoint == "playlistItems":
            items = [{"contentDetails": {"videoId": i}, "snippet": {"publishedAt": "2026-10-01T00:00:00Z"}} for i in self.uploads]
        else:
            raise AssertionError(endpoint)
        return httpx.Response(200, json={"items": items})

    def client(self) -> YouTubeClient:
        return YouTubeClient("key", http_client=httpx.Client(transport=self))

    def params(self, endpoint: str) -> list[dict]:
        return [p for e, p in self.calls if e == endpoint]


# ── parsing ──

@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=abc123DEF45",
    "https://youtu.be/abc123DEF45",
    "https://www.youtube.com/shorts/abc123DEF45",
    "https://m.youtube.com/watch?v=abc123DEF45&t=12s",
])
def test_video_id_from_any_youtube_link(url):
    assert extract_youtube_video_id(url) == "abc123DEF45"


def test_video_id_rejects_other_sites():
    with pytest.raises(ValueError):
        extract_youtube_video_id("https://example.com/watch?v=abc123DEF45")


@pytest.mark.parametrize("text,seconds", [("PT45S", 45), ("PT1M5S", 65), ("PT1H2M3S", 3723), ("P1DT2H3M4S", 93784)])
def test_iso_durations(text, seconds):
    assert parse_iso8601_duration_seconds(text) == seconds


@pytest.mark.parametrize("query,kind,value", [
    ("@creator", "handle", "@creator"),
    ("https://www.youtube.com/@creator", "handle", "@creator"),
    (f"https://www.youtube.com/channel/{CHANNEL}", "id", CHANNEL),
    (CHANNEL, "id", CHANNEL),
    ("슈카월드", "query", "슈카월드"),
])
def test_channel_identifier(query, kind, value):
    assert extract_youtube_channel_identifier(query) == (kind, value)


def test_ratio_sort_puts_unknown_subscribers_last():
    def c(video_id, views, subs):
        return ReferenceCandidate(video_id=video_id, url=f"https://www.youtube.com/watch?v={video_id}", title=video_id,
                                  channel_id="c", channel_name="채널", thumbnail_url="https://example.com/t.jpg", upload_date="2026-10-01T00:00:00Z",
                                  duration_seconds=45, view_count=views, subscriber_count=subs, source_type="search")
    ordered = sort_by_vs_ratio([c("low", 1000, 1000), c("none", 100000, None), c("high", 5000, 100)])
    assert [x.video_id for x in ordered] == ["high", "low", "none"]


def test_date_range_splits_into_weeks_counting_back():
    request = ReferenceSearchRequest(keyword="과학", published_after="2026-08-01", published_before="2026-08-15")
    assert date_windows(request) == [("2026-08-01", "2026-08-01"), ("2026-08-02", "2026-08-08"), ("2026-08-09", "2026-08-15")]


# ── search ──

def test_search_fills_in_duration_views_and_subscribers():
    [hit] = FakeAPI([vid("abc123DEF45")]).client().search(ReferenceSearchRequest(keyword="테스트"))
    assert (hit.video_id, hit.duration_seconds, hit.view_count, hit.subscriber_count, hit.vs_ratio) == ("abc123DEF45", 45, 120000, 3000, 40)


def test_over_five_minutes_filter():
    api = FakeAPI([vid("abc123DEF45", "짧은 영상"), vid("xyz987ABCDE", "긴 영상", duration="PT6M1S", views=90000)])
    results = api.client().search(ReferenceSearchRequest(keyword="테스트", duration_filter="over_300"))
    assert [r.video_id for r in results] == ["xyz987ABCDE"]


def test_long_date_range_searches_each_window():
    windows = {
        ("2026-08-01T00:00:00Z", "2026-08-01T23:59:59Z"): "day123DEF45",
        ("2026-08-02T00:00:00Z", "2026-08-08T23:59:59Z"): "week12DEF45",
        ("2026-08-09T00:00:00Z", "2026-08-15T23:59:59Z"): "week23DEF45",
    }
    hit = windows.get
    api = FakeAPI(
        [vid("day123DEF45", views=9000, published="2026-08-01T00:00:00Z"),
         vid("week12DEF45", views=30000, published="2026-08-08T00:00:00Z"),
         vid("week23DEF45", views=12000, published="2026-08-15T00:00:00Z")],
        subscribers={"channel-1": 1000},
        found=lambda p: [i] if (i := hit((p.get("publishedAfter"), p.get("publishedBefore")))) else [],
    )
    request = ReferenceSearchRequest(keyword="과학", published_after="2026-08-01", published_before="2026-08-15", max_results=50)
    assert {r.video_id for r in api.client().search(request)} == set(windows.values())


def test_items_missing_metadata_are_skipped():
    api = FakeAPI([{"id": "bad123DEF45"}, vid("abc123DEF45")])
    assert [r.video_id for r in api.client().search(ReferenceSearchRequest(keyword="테스트"))] == ["abc123DEF45"]


def test_direct_link_to_a_missing_video():
    with pytest.raises(ValueError, match="not found or unavailable"):
        FakeAPI(subscribers={}).client().get_direct("https://www.youtube.com/watch?v=abc123DEF45")


def test_channel_only_lists_its_uploads():
    api = FakeAPI([vid("chan123DEF45", "채널 업로드 영상", duration="PT50S", views=150000, channel=CHANNEL)],
                  subscribers={CHANNEL: 50000}, uploads=["chan123DEF45"])
    [hit] = api.client().search(ReferenceSearchRequest(channel_query="@creator"))
    assert (hit.video_id, hit.title, hit.vs_ratio) == ("chan123DEF45", "채널 업로드 영상", 3.0)
    assert api.params("playlistItems")[0]["playlistId"] == UPLOADS


def test_channel_plus_keyword_searches_inside_the_channel():
    api = FakeAPI([vid("filt123DEF45", duration="PT30S", views=50000, channel=CHANNEL)], subscribers={CHANNEL: 10000})
    [hit] = api.client().search(ReferenceSearchRequest(keyword="투자", channel_query=CHANNEL))
    assert hit.video_id == "filt123DEF45"
    assert api.params("search")[0]["channelId"] == CHANNEL and api.params("search")[0]["q"] == "투자"


def test_search_request_shape():
    api = FakeAPI(found=lambda p: [])
    api.client().search(ReferenceSearchRequest(keyword="돈", duration_filter="under_180"))
    api.client().search(ReferenceSearchRequest(keyword="돈", duration_filter="under_300"))
    first, last = api.params("search")[0], api.params("search")[-1]
    assert first["videoDuration"] == "short" and first["maxResults"] == "50"
    assert "regionCode" not in first  # worldwide
    assert "videoDuration" not in last  # YouTube's "short" is under 4 minutes


def test_each_comma_keyword_is_its_own_search():
    api = FakeAPI(found=lambda p: [])
    api.client().search(ReferenceSearchRequest(keyword="실화 썰, true story ,実話,,a,b,c,d,e,f,g"))
    assert [p["q"] for p in api.params("search")] == ["실화 썰", "true story", "実話", "a", "b", "c", "d", "e", "f"]  # capped at 9


# ── language filters ──

@pytest.mark.parametrize("snip,keep", [
    ({"title": "돈이 모이는 습관", "defaultAudioLanguage": "ko"}, True),
    ({"title": "5 Habits to 10x your Money"}, True),
    ({"title": "お金が貯まる習慣", "defaultAudioLanguage": "ja"}, True),
    ({"title": "理财习惯", "defaultAudioLanguage": "zh-Hans"}, True),
    ({"title": "Unknown language", "defaultAudioLanguage": "und"}, True),
    ({"title": "Money habits in English title", "defaultAudioLanguage": "hi"}, False),
    ({"title": "డబ్బు సంపాదించే 6 పనులు"}, False),
    ({"title": "पैसे की आदतें"}, False),
])
def test_readable_languages(snip, keep):
    assert is_readable_language(snip) is keep


def test_channel_country_and_script():
    assert is_readable_channel({"country": "US", "description": "Money tips"})
    assert is_readable_channel({})
    assert not is_readable_channel({"country": "IN", "description": "Money tips"})
    assert not is_readable_channel({"description": "డబ్బు చిట్కాలు"})
