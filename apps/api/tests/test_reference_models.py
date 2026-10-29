"""Reference request and candidate validation."""
import pytest
from pydantic import ValidationError

from app.references.models import DirectReferenceRequest, ReferenceCandidate, ReferenceSearchRequest, SelectReferenceRequest

VIDEO = dict(video_id="abc123DEF45", url="https://www.youtube.com/watch?v=abc123DEF45", title="테스트 쇼츠",
             channel_id="channel-1", channel_name="채널", thumbnail_url="https://img.youtube.com/vi/abc123DEF45/default.jpg",
             upload_date="2026-10-01T00:00:00Z", duration_seconds=45, view_count=120000, subscriber_count=3000, source_type="search")


def test_ratio_is_views_per_subscriber():
    assert ReferenceCandidate(**VIDEO).vs_ratio == 40.0
    assert ReferenceCandidate(**{**VIDEO, "subscriber_count": None, "source_type": "direct"}).vs_ratio is None


@pytest.mark.parametrize("override", [
    {"video_id": " "}, {"url": " "}, {"title": " "}, {"channel_id": " "}, {"channel_name": " "},
    {"thumbnail_url": " "}, {"upload_date": " "}, {"duration_seconds": -1}, {"view_count": -1}, {"subscriber_count": -1},
])
def test_candidate_core_fields(override):
    with pytest.raises(ValidationError):
        ReferenceCandidate(**{**VIDEO, **override})


@pytest.mark.parametrize("preset,limit", [("under_60", 60), ("under_120", 120), ("under_180", 180),
                                          ("under_300", 300), ("over_300", None), ("all", None)])
def test_duration_presets(preset, limit):
    request = ReferenceSearchRequest(keyword="ai", duration_filter=preset)
    assert (request.duration_filter, request.effective_max_duration_seconds) == (preset, limit)


@pytest.mark.parametrize("build", [
    lambda: ReferenceSearchRequest(keyword="ai", max_results=101),
    lambda: ReferenceSearchRequest(keyword="ai", duration_filter="short"),
    lambda: ReferenceSearchRequest(keyword="   "),
    lambda: DirectReferenceRequest(url="   "),
    lambda: SelectReferenceRequest(video_id="   "),
])
def test_bad_requests(build):
    with pytest.raises(ValidationError):
        build()
