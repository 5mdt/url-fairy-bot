# metrics_test.py

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app import metrics
from app.bot import _deliver_result
from app.config import settings
from app.download import UnsupportedUrlError, yt_dlp_download
from app.main import app
from app.url_processing import DownloadResult, process_url_request


@pytest.fixture(autouse=True)
def no_redirects(monkeypatch):
    monkeypatch.setattr("app.url_processing.follow_redirects", lambda url: url)


# #UFB-0045
@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.youtube.com/watch?v=abc", "youtube"),
        ("https://youtu.be/abc", "youtube"),
        ("https://vm.tiktok.com/x", "tiktok"),
        ("https://x.com/u/status/1", "twitter"),
        ("https://open.spotify.com/track/1", "spotify"),
        ("https://notyoutube.com/a", "other"),
        ("https://example.org/a", "other"),
        ("not a url", "other"),
    ],
)
def test_platform_for_returns_fixed_names(url, expected):
    assert metrics.platform_for(url) == expected
    assert metrics.platform_for(url) in metrics.PLATFORMS


# #UFB-0045
def test_unknown_platform_label_collapses_to_other():
    metrics.record_request("https://secret.example/1")
    assert metrics.requests_total() == {"other": 1}


# #UFB-0045
def test_unknown_outcome_downloader_and_kind_are_rejected():
    with pytest.raises(ValueError):
        metrics.record_download_outcome("youtube", "weird")
    with pytest.raises(ValueError):
        metrics.record_downloader("curl")
    with pytest.raises(ValueError):
        metrics.record_reply_kind("carrier-pigeon")


# #UFB-0045
@pytest.mark.asyncio
async def test_counter_increments_once_and_labels_hold_no_url_or_chat_id():
    url = "https://www.tiktok.com/@secretuser/video/123456789"
    result = DownloadResult(text="t", media_path="/tmp/x.mp4")
    with patch(
        "app.url_processing.attempt_download", new=AsyncMock(return_value=result)
    ):
        await process_url_request(url)

    assert metrics.requests_total() == {"tiktok": 1}
    assert metrics.download_outcomes() == {"tiktok": {"success": 1}}
    text = metrics.render().decode()
    assert "secretuser" not in text and "123456789" not in text
    assert "http" not in text


# #UFB-0045
@pytest.mark.asyncio
async def test_failed_download_with_mirror_is_one_failure_and_one_fallback():
    url = "https://www.tiktok.com/@u/video/1"
    with patch(
        "app.url_processing.attempt_download",
        new=AsyncMock(side_effect=UnsupportedUrlError("nope")),
    ):
        await process_url_request(url)

    assert metrics.download_outcomes() == {
        "tiktok": {"failure": 1, "fallback_mirror": 1}
    }
    assert metrics.requests_total() == {"tiktok": 1}


# #UFB-0045
@pytest.mark.asyncio
async def test_failed_download_without_mirror_is_only_a_failure():
    with patch(
        "app.url_processing.attempt_download",
        new=AsyncMock(side_effect=UnsupportedUrlError("nope")),
    ):
        await process_url_request("https://example.org/v")

    assert metrics.download_outcomes() == {"other": {"failure": 1}}


# #UFB-0045
@pytest.mark.asyncio
async def test_disallowed_domain_counts_a_request_but_no_download(monkeypatch):
    monkeypatch.setattr(settings, "DOWNLOAD_ALLOWED_DOMAINS", "youtube.com")
    await process_url_request("https://example.org/v")

    assert metrics.requests_total() == {"other": 1}
    assert metrics.download_outcomes() == {}


# #UFB-0045
@pytest.mark.asyncio
async def test_download_latency_is_observed():
    result = DownloadResult(text="t", media_path=None)
    with patch(
        "app.url_processing.attempt_download", new=AsyncMock(return_value=result)
    ):
        await process_url_request("https://youtu.be/abc")

    text = metrics.render().decode()
    assert 'ufb_download_seconds_count{platform="youtube"} 1.0' in text


# #UFB-0045
@pytest.mark.asyncio
async def test_yt_dlp_download_records_cache_miss_downloader_then_hit(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "COOKIES_DIR", str(tmp_path))
    url = "https://tiktok.com/@user/video/1"
    from app.download import url_to_filename_stem

    expected = tmp_path / f"{url_to_filename_stem(url)}.mp4"
    instance = MagicMock()
    instance.download.side_effect = lambda urls: expected.write_text("x" * 100)
    ydl = MagicMock()
    ydl.__enter__.return_value = instance
    with (
        patch("app.download.yt_dlp.YoutubeDL", return_value=ydl),
        patch("app.download.media.normalize_if_quiet"),
    ):
        await yt_dlp_download(url)
        assert metrics.cache_hit_rate() == 0.0
        await yt_dlp_download(url)

    assert metrics.cache_hit_rate() == 0.5
    assert metrics.downloader_successes() == {"yt-dlp": 1}
    assert metrics.cache_size_bytes() == 100


# #UFB-0045
def test_cache_hit_rate_is_none_before_any_lookup():
    assert metrics.cache_hit_rate() is None


# #UFB-0045
@pytest.mark.asyncio
async def test_reply_kind_native_video_and_text_link():
    message = MagicMock()
    message.reply = AsyncMock()
    result = DownloadResult(text="c", media_path="/tmp/clip.mp4")
    with (
        patch("app.bot.os.path.getsize", return_value=1024),
        patch("app.bot._reply_with_video", new=AsyncMock(return_value=True)),
    ):
        await _deliver_result(message, result)
    with (
        patch("app.bot.os.path.getsize", return_value=1024),
        patch("app.bot._reply_with_video", new=AsyncMock(return_value=False)),
    ):
        await _deliver_result(message, result)
    await _deliver_result(message, "plain")

    assert metrics.reply_kinds() == {"native_video": 1, "text_link": 2}
    assert 'ufb_reply_seconds_count{kind="text_link"} 2.0' in metrics.render().decode()


# #UFB-0045
@pytest.mark.asyncio
async def test_failed_reply_is_timed_but_not_counted():
    message = MagicMock()
    message.reply = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        await _deliver_result(message, "plain")

    assert metrics.reply_kinds() == {}
    assert 'ufb_reply_seconds_count{kind="text_link"} 1.0' in metrics.render().decode()


# #UFB-0045
def test_snapshot_has_all_headline_numbers():
    metrics.record_request("youtube")
    assert set(metrics.snapshot()) == {
        "requests",
        "downloads",
        "downloaders",
        "replies",
        "cache_hit_rate",
        "cache_size_bytes",
    }


# #UFB-0045
@pytest.mark.asyncio
async def test_metrics_endpoint_serves_prometheus_text():
    metrics.record_request("youtube")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert 'ufb_requests_total{platform="youtube"} 1.0' in response.text
    assert "ufb_cache_size_bytes" in response.text
