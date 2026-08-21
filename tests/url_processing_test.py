# url_processing_test.py

from unittest.mock import AsyncMock, patch

import pytest
import requests

from app.config import settings
from app.download import UnsupportedUrlError
from app.url_processing import (
    apply_rewrite_map,
    attempt_download,
    follow_redirects,
    is_domain_allowed,
    process_url_request,
    transform_youtube_url,
)

# --- apply_rewrite_map: defaults ---


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://open.spotify.com/track/abc", "https://fxspotify.com/track/abc"),
        ("https://spotify.com/track/abc", "https://fxspotify.com/track/abc"),
        (
            "https://www.instagram.com/p/abc123/",
            "https://www.kkinstagram.com/p/abc123/",
        ),
        (
            "https://instagram.com/reel/abc123/",
            "https://www.kkinstagram.com/reel/abc123/",
        ),
        (
            "https://www.reddit.com/r/foo/comments/abc",
            "https://rxddit.com/r/foo/comments/abc",
        ),
        (
            "https://www.tiktok.com/@user/video/123",
            "https://tfxktok.com/@user/video/123",
        ),
        (
            "https://twitter.com/user/status/123",
            "https://www.fxtwitter.com/user/status/123",
        ),
        ("https://x.com/user/status/123", "https://www.fxtwitter.com/user/status/123"),
        ("https://example.com/foo", "https://example.com/foo"),
    ],
)
def test_apply_rewrite_map_defaults(url, expected):
    assert apply_rewrite_map(url) == expected


# --- apply_rewrite_map: overridden via settings ---


def test_apply_rewrite_map_respects_overridden_settings(monkeypatch):
    monkeypatch.setattr(settings, "SPOTIFY_MIRROR_DOMAIN", "spotify.mirror.example")
    monkeypatch.setattr(settings, "TWITTER_MIRROR_DOMAIN", "twitter.mirror.example")

    assert (
        apply_rewrite_map("https://open.spotify.com/track/abc")
        == "https://spotify.mirror.example/track/abc"
    )
    assert (
        apply_rewrite_map("https://x.com/user/status/123")
        == "https://www.twitter.mirror.example/user/status/123"
    )


# --- transform_youtube_url: defaults ---


@pytest.mark.parametrize(
    "url,expected",
    [
        (
            "https://music.youtube.com/watch?v=abc123",
            "https://music.yfxtube.com/watch?v=abc123",
        ),
        (
            "https://www.youtube.com/watch?v=abc123",
            "https://www.yfxtube.com/watch?v=abc123",
        ),
        ("https://youtu.be/abc123", "https://fxyoutu.be/abc123"),
        ("https://example.com/watch?v=abc123", None),
    ],
)
def test_transform_youtube_url_defaults(url, expected):
    assert transform_youtube_url(url) == expected


# --- transform_youtube_url: overridden via settings ---


def test_transform_youtube_url_respects_overridden_settings(monkeypatch):
    monkeypatch.setattr(settings, "YOUTUBE_MIRROR_DOMAIN", "yt.mirror.example")
    monkeypatch.setattr(settings, "YOUTUBE_SHORT_MIRROR_DOMAIN", "yt.short.example")

    assert (
        transform_youtube_url("https://www.youtube.com/watch?v=abc123")
        == "https://www.yt.mirror.example/watch?v=abc123"
    )
    assert (
        transform_youtube_url("https://music.youtube.com/watch?v=abc123")
        == "https://music.yt.mirror.example/watch?v=abc123"
    )
    assert (
        transform_youtube_url("https://youtu.be/abc123")
        == "https://yt.short.example/abc123"
    )


# --- transform_youtube_url: coverage gaps (BUGS.md #26) ---


@pytest.mark.xfail(
    strict=True,
    reason="BUGS.md #26: YouTube rewrite misses Shorts/m./bare-domain forms",
)
@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/shorts/abc123",
        "https://m.youtube.com/watch?v=abc123",
        "https://youtube.com/watch?v=abc123",
    ],
)
def test_transform_youtube_url_missing_forms(url):
    assert transform_youtube_url(url) is not None


# --- is_domain_allowed ---


def test_is_domain_allowed_exact_and_subdomain_match(monkeypatch):
    monkeypatch.setattr(settings, "DOWNLOAD_ALLOWED_DOMAINS", "tiktok.com,example.org")

    assert is_domain_allowed("https://tiktok.com/@user/video/1") is True
    assert is_domain_allowed("https://vt.tiktok.com/abc") is True
    assert is_domain_allowed("https://www.example.org/foo") is True
    assert is_domain_allowed("https://not-allowed.com/foo") is False


def test_is_domain_allowed_strips_www(monkeypatch):
    monkeypatch.setattr(settings, "DOWNLOAD_ALLOWED_DOMAINS", "example.com")
    assert is_domain_allowed("https://www.example.com/foo") is True


def test_is_domain_allowed_empty_allowlist_rejects_everything(monkeypatch):
    monkeypatch.setattr(settings, "DOWNLOAD_ALLOWED_DOMAINS", "")
    assert is_domain_allowed("https://tiktok.com/@user/video/1") is False


@pytest.mark.xfail(
    strict=True,
    reason="BUGS.md #5: endswith() is a substring match, not a label-boundary match",
)
def test_is_domain_allowed_rejects_lookalike_domain(monkeypatch):
    monkeypatch.setattr(settings, "DOWNLOAD_ALLOWED_DOMAINS", "tiktok.com")
    assert is_domain_allowed("https://evil-tiktok.com/x") is False


# --- follow_redirects ---


def test_follow_redirects_resolves_and_strips_query():
    mock_response = type("R", (), {"url": "https://final.example.com/path?foo=bar"})()
    with patch("requests.head", return_value=mock_response):
        assert follow_redirects("https://short.example.com/x") == (
            "https://final.example.com/path"
        )


def test_follow_redirects_returns_original_on_timeout():
    with patch("requests.head", side_effect=requests.Timeout):
        assert (
            follow_redirects("https://slow.example.com/x")
            == "https://slow.example.com/x"
        )


def test_follow_redirects_returns_original_on_invalid_redirect_target():
    mock_response = type("R", (), {"url": "not-a-valid-url"})()
    with patch("requests.head", return_value=mock_response):
        assert (
            follow_redirects("https://short.example.com/x")
            == "https://short.example.com/x"
        )


@pytest.mark.xfail(
    strict=True,
    reason="BUGS.md #1: query string is unconditionally stripped, breaking YouTube rewrites",
)
def test_follow_redirects_preserves_query_string():
    mock_response = type("R", (), {"url": "https://www.youtube.com/watch?v=abc123"})()
    with patch("requests.head", return_value=mock_response):
        assert follow_redirects("https://short.example.com/x") == (
            "https://www.youtube.com/watch?v=abc123"
        )


@pytest.mark.xfail(
    strict=True,
    reason="BUGS.md #11: only requests.Timeout is caught; other request errors propagate",
)
def test_follow_redirects_handles_connection_error():
    with patch("requests.head", side_effect=requests.ConnectionError):
        assert follow_redirects("https://unreachable.example.com/x") == (
            "https://unreachable.example.com/x"
        )


# --- apply_rewrite_map: security case (BUGS.md #22) ---


@pytest.mark.xfail(
    strict=True, reason="BUGS.md #22: unescaped '.' in spotify.com pattern"
)
def test_apply_rewrite_map_does_not_match_spoofed_spotify_domain():
    url = "https://spotifyXcom.evil.tld/track/abc"
    assert apply_rewrite_map(url) == url


# --- apply_rewrite_map: per-platform toggles (BUGS.md #2) ---


@pytest.mark.xfail(
    strict=True, reason="BUGS.md #2: *_REWRITE_ENABLED flags are never read"
)
def test_apply_rewrite_map_respects_tiktok_disabled(monkeypatch):
    monkeypatch.setattr(settings, "TIKTOK_REWRITE_ENABLED", False)
    url = "https://www.tiktok.com/@user/video/123"
    assert apply_rewrite_map(url) == url


# --- attempt_download ---


@pytest.mark.asyncio
async def test_attempt_download_success(monkeypatch):
    monkeypatch.setattr(settings, "BASE_URL", "example.test")
    with patch(
        "app.url_processing.yt_dlp_download",
        new=AsyncMock(return_value="/cache/some_video.mp4"),
    ):
        result = await attempt_download("https://tiktok.com/@user/video/1")

    assert "example.test/some_video.mp4" in result
    assert "https://tiktok.com/@user/video/1" in result


@pytest.mark.asyncio
async def test_attempt_download_propagates_unsupported_url_error():
    with patch(
        "app.url_processing.yt_dlp_download",
        new=AsyncMock(side_effect=UnsupportedUrlError("nope")),
    ):
        with pytest.raises(UnsupportedUrlError):
            await attempt_download("https://tiktok.com/@user/video/1")


@pytest.mark.asyncio
async def test_attempt_download_wraps_unexpected_exception():
    with patch(
        "app.url_processing.yt_dlp_download",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        with pytest.raises(UnsupportedUrlError):
            await attempt_download("https://tiktok.com/@user/video/1")


@pytest.mark.asyncio
async def test_attempt_download_returns_none_when_no_path():
    with patch("app.url_processing.yt_dlp_download", new=AsyncMock(return_value=None)):
        assert await attempt_download("https://tiktok.com/@user/video/1") is None


# --- process_url_request: full branch matrix ---


@pytest.mark.asyncio
async def test_process_url_request_disallowed_no_rewrite_private():
    with patch(
        "app.url_processing.follow_redirects", return_value="https://example.com/x"
    ):
        result = await process_url_request("https://example.com/x", is_group_chat=False)
    assert "not allowed for downloading" in result
    assert "example.com/x" in result


@pytest.mark.asyncio
async def test_process_url_request_disallowed_no_rewrite_group_is_silent():
    with patch(
        "app.url_processing.follow_redirects", return_value="https://example.com/x"
    ):
        result = await process_url_request("https://example.com/x", is_group_chat=True)
    assert result is None


@pytest.mark.asyncio
async def test_process_url_request_disallowed_with_rewrite_private():
    with patch(
        "app.url_processing.follow_redirects",
        return_value="https://www.tiktok.com/@user/video/1",
    ):
        result = await process_url_request(
            "https://www.tiktok.com/@user/video/1", is_group_chat=False
        )
    assert "alternative link" in result
    assert "tfxktok.com" in result


@pytest.mark.asyncio
async def test_process_url_request_disallowed_with_rewrite_group():
    with patch(
        "app.url_processing.follow_redirects",
        return_value="https://www.tiktok.com/@user/video/1",
    ):
        result = await process_url_request(
            "https://www.tiktok.com/@user/video/1", is_group_chat=True
        )
    assert "tfxktok.com" in result


@pytest.mark.asyncio
async def test_process_url_request_youtube_short_circuits(monkeypatch):
    monkeypatch.setattr(settings, "DOWNLOAD_ALLOWED_DOMAINS", "youtube.com")
    with patch(
        "app.url_processing.follow_redirects",
        return_value="https://www.youtube.com/watch?v=abc123",
    ):
        result = await process_url_request(
            "https://www.youtube.com/watch?v=abc123", is_group_chat=False
        )
    assert "cannot be downloaded" in result
    assert "yfxtube.com" in result


@pytest.mark.asyncio
async def test_process_url_request_allowed_download_succeeds(monkeypatch):
    monkeypatch.setattr(settings, "DOWNLOAD_ALLOWED_DOMAINS", "tiktok.com")
    monkeypatch.setattr(settings, "BASE_URL", "example.test")
    with (
        patch(
            "app.url_processing.follow_redirects",
            return_value="https://www.tiktok.com/@user/video/1",
        ),
        patch(
            "app.url_processing.yt_dlp_download",
            new=AsyncMock(return_value="/cache/vid.mp4"),
        ),
    ):
        result = await process_url_request(
            "https://www.tiktok.com/@user/video/1", is_group_chat=False
        )
    assert "example.test/vid.mp4" in result


@pytest.mark.asyncio
async def test_process_url_request_allowed_download_unsupported_with_rewrite(
    monkeypatch,
):
    monkeypatch.setattr(settings, "DOWNLOAD_ALLOWED_DOMAINS", "tiktok.com")
    with (
        patch(
            "app.url_processing.follow_redirects",
            return_value="https://www.tiktok.com/@user/video/1",
        ),
        patch(
            "app.url_processing.yt_dlp_download",
            new=AsyncMock(side_effect=UnsupportedUrlError("nope")),
        ),
    ):
        result = await process_url_request(
            "https://www.tiktok.com/@user/video/1", is_group_chat=False
        )
    assert "tfxktok.com" in result


@pytest.mark.asyncio
async def test_process_url_request_allowed_download_unsupported_no_rewrite_group_silent(
    monkeypatch,
):
    monkeypatch.setattr(settings, "DOWNLOAD_ALLOWED_DOMAINS", "example.com")
    with (
        patch(
            "app.url_processing.follow_redirects", return_value="https://example.com/x"
        ),
        patch(
            "app.url_processing.yt_dlp_download",
            new=AsyncMock(side_effect=UnsupportedUrlError("nope")),
        ),
    ):
        result = await process_url_request("https://example.com/x", is_group_chat=True)
    assert result is None


@pytest.mark.skip(
    reason=(
        "app/url_processing.py:167-179 (the generic `except Exception` branch) is "
        "unreachable: attempt_download() is the only call inside the try block and it "
        "converts every exception into UnsupportedUrlError, so the `except "
        "UnsupportedUrlError` branch above always wins. Not yet recorded in docs/BUGS.md."
    )
)
@pytest.mark.asyncio
async def test_process_url_request_allowed_download_unexpected_exception():
    pass
