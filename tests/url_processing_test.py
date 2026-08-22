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
    is_rewrite_allowed,
    process_url_request,
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
        (
            "https://music.youtube.com/watch?v=abc123",
            "https://music.yfxtube.com/watch?v=abc123",
        ),
        (
            "https://www.youtube.com/watch?v=abc123",
            "https://www.yfxtube.com/watch?v=abc123",
        ),
        ("https://youtu.be/abc123", "https://fxyoutu.be/abc123"),
        ("https://example.com/foo", "https://example.com/foo"),
    ],
)
def test_apply_rewrite_map_defaults(url, expected):
    assert apply_rewrite_map(url) == expected


# --- apply_rewrite_map: coverage gaps (BUGS.md #26) ---


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/shorts/abc123",
        "https://m.youtube.com/watch?v=abc123",
        "https://youtube.com/watch?v=abc123",
    ],
)
def test_apply_rewrite_map_youtube_missing_forms(url):
    assert apply_rewrite_map(url) != url


# --- apply_rewrite_map: overridden via settings ---


def test_apply_rewrite_map_respects_overridden_settings(monkeypatch):
    monkeypatch.setattr(settings, "SPOTIFY_MIRROR_DOMAIN", "spotify.mirror.example")
    monkeypatch.setattr(settings, "TWITTER_MIRROR_DOMAIN", "twitter.mirror.example")
    monkeypatch.setattr(settings, "YOUTUBE_MIRROR_DOMAIN", "yt.mirror.example")
    monkeypatch.setattr(settings, "YOUTUBE_SHORT_MIRROR_DOMAIN", "yt.short.example")

    assert (
        apply_rewrite_map("https://open.spotify.com/track/abc")
        == "https://spotify.mirror.example/track/abc"
    )
    assert (
        apply_rewrite_map("https://x.com/user/status/123")
        == "https://www.twitter.mirror.example/user/status/123"
    )
    assert (
        apply_rewrite_map("https://www.youtube.com/watch?v=abc123")
        == "https://www.yt.mirror.example/watch?v=abc123"
    )
    assert (
        apply_rewrite_map("https://music.youtube.com/watch?v=abc123")
        == "https://music.yt.mirror.example/watch?v=abc123"
    )
    assert (
        apply_rewrite_map("https://youtu.be/abc123")
        == "https://yt.short.example/abc123"
    )


# --- apply_rewrite_map: REWRITE_ALLOWED_DOMAINS gating ---


def test_apply_rewrite_map_respects_rewrite_allowed_domains(monkeypatch):
    monkeypatch.setattr(settings, "REWRITE_ALLOWED_DOMAINS", "spotify.com")
    assert (
        apply_rewrite_map("https://www.tiktok.com/@user/video/123")
        == "https://www.tiktok.com/@user/video/123"
    )
    assert (
        apply_rewrite_map("https://www.youtube.com/watch?v=abc123")
        == "https://www.youtube.com/watch?v=abc123"
    )
    assert (
        apply_rewrite_map("https://open.spotify.com/track/abc")
        == "https://fxspotify.com/track/abc"
    )


def test_apply_rewrite_map_empty_rewrite_allowed_domains_allows_everything(monkeypatch):
    monkeypatch.setattr(settings, "REWRITE_ALLOWED_DOMAINS", "")
    assert (
        apply_rewrite_map("https://www.tiktok.com/@user/video/123")
        == "https://tfxktok.com/@user/video/123"
    )


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


def test_is_domain_allowed_empty_allowlist_allows_everything(monkeypatch):
    monkeypatch.setattr(settings, "DOWNLOAD_ALLOWED_DOMAINS", "")
    assert is_domain_allowed("https://tiktok.com/@user/video/1") is True


def test_is_domain_allowed_rejects_lookalike_domain(monkeypatch):
    monkeypatch.setattr(settings, "DOWNLOAD_ALLOWED_DOMAINS", "tiktok.com")
    assert is_domain_allowed("https://evil-tiktok.com/x") is False


# --- is_rewrite_allowed ---


def test_is_rewrite_allowed_exact_and_subdomain_match(monkeypatch):
    monkeypatch.setattr(settings, "REWRITE_ALLOWED_DOMAINS", "tiktok.com,example.org")

    assert is_rewrite_allowed("https://tiktok.com/@user/video/1") is True
    assert is_rewrite_allowed("https://vt.tiktok.com/abc") is True
    assert is_rewrite_allowed("https://www.example.org/foo") is True
    assert is_rewrite_allowed("https://not-allowed.com/foo") is False


def test_is_rewrite_allowed_empty_allowlist_allows_everything(monkeypatch):
    monkeypatch.setattr(settings, "REWRITE_ALLOWED_DOMAINS", "")
    assert is_rewrite_allowed("https://youtube.com/watch?v=abc123") is True


def test_is_rewrite_allowed_rejects_lookalike_domain(monkeypatch):
    monkeypatch.setattr(settings, "REWRITE_ALLOWED_DOMAINS", "tiktok.com")
    assert is_rewrite_allowed("https://evil-tiktok.com/x") is False


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


def test_follow_redirects_preserves_query_string():
    mock_response = type("R", (), {"url": "https://www.youtube.com/watch?v=abc123"})()
    with patch("requests.head", return_value=mock_response):
        assert follow_redirects("https://short.example.com/x") == (
            "https://www.youtube.com/watch?v=abc123"
        )


def test_follow_redirects_handles_connection_error():
    with patch("requests.head", side_effect=requests.ConnectionError):
        assert follow_redirects("https://unreachable.example.com/x") == (
            "https://unreachable.example.com/x"
        )


# --- apply_rewrite_map: security case (BUGS.md #22) ---


def test_apply_rewrite_map_does_not_match_spoofed_spotify_domain():
    url = "https://spotifyXcom.evil.tld/track/abc"
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
async def test_process_url_request_disallowed_no_rewrite_private(monkeypatch):
    monkeypatch.setattr(settings, "DOWNLOAD_ALLOWED_DOMAINS", "tiktok.com")
    with patch(
        "app.url_processing.follow_redirects", return_value="https://example.com/x"
    ):
        result = await process_url_request("https://example.com/x", is_group_chat=False)
    assert "not allowed for downloading" in result
    assert "example.com/x" in result


@pytest.mark.asyncio
async def test_process_url_request_disallowed_no_rewrite_group_is_silent(monkeypatch):
    monkeypatch.setattr(settings, "DOWNLOAD_ALLOWED_DOMAINS", "tiktok.com")
    with patch(
        "app.url_processing.follow_redirects", return_value="https://example.com/x"
    ):
        result = await process_url_request("https://example.com/x", is_group_chat=True)
    assert result is None


@pytest.mark.asyncio
async def test_process_url_request_disallowed_with_rewrite_private(monkeypatch):
    monkeypatch.setattr(settings, "DOWNLOAD_ALLOWED_DOMAINS", "example.com")
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
async def test_process_url_request_disallowed_with_rewrite_group(monkeypatch):
    monkeypatch.setattr(settings, "DOWNLOAD_ALLOWED_DOMAINS", "example.com")
    with patch(
        "app.url_processing.follow_redirects",
        return_value="https://www.tiktok.com/@user/video/1",
    ):
        result = await process_url_request(
            "https://www.tiktok.com/@user/video/1", is_group_chat=True
        )
    assert "tfxktok.com" in result


@pytest.mark.asyncio
async def test_process_url_request_disallowed_download_allows_everything_by_default():
    # Default (empty) DOWNLOAD_ALLOWED_DOMAINS means every domain is allowed
    # for download — a real download is attempted rather than a mirror
    # offered.
    with (
        patch(
            "app.url_processing.follow_redirects",
            return_value="https://example.com/x",
        ),
        patch(
            "app.url_processing.yt_dlp_download",
            new=AsyncMock(return_value="/cache/vid.mp4"),
        ) as mock_download,
    ):
        result = await process_url_request("https://example.com/x", is_group_chat=False)
    mock_download.assert_called_once()
    assert "vid.mp4" in result


@pytest.mark.asyncio
async def test_process_url_request_youtube_downloads_by_default(monkeypatch):
    # YouTube is no longer special-cased: with the default (empty)
    # DOWNLOAD_ALLOWED_DOMAINS, a YouTube URL is downloaded like any other
    # platform rather than mirrored.
    monkeypatch.setattr(settings, "BASE_URL", "example.test")
    with (
        patch(
            "app.url_processing.follow_redirects",
            return_value="https://www.youtube.com/watch?v=abc123",
        ),
        patch(
            "app.url_processing.yt_dlp_download",
            new=AsyncMock(return_value="/cache/vid.mp4"),
        ) as mock_download,
    ):
        result = await process_url_request(
            "https://www.youtube.com/watch?v=abc123", is_group_chat=False
        )
    mock_download.assert_called_once()
    assert "example.test/vid.mp4" in result


@pytest.mark.asyncio
async def test_process_url_request_youtube_mirrored_when_download_disallowed(
    monkeypatch,
):
    monkeypatch.setattr(settings, "DOWNLOAD_ALLOWED_DOMAINS", "tiktok.com")
    with (
        patch(
            "app.url_processing.follow_redirects",
            return_value="https://www.youtube.com/watch?v=abc123",
        ),
        patch("app.url_processing.yt_dlp_download", new=AsyncMock()) as mock_download,
    ):
        result = await process_url_request(
            "https://www.youtube.com/watch?v=abc123", is_group_chat=False
        )
    mock_download.assert_not_called()
    assert "alternative link" in result
    assert "yfxtube.com" in result


@pytest.mark.asyncio
async def test_process_url_request_youtube_no_mirror_when_both_disallowed(
    monkeypatch,
):
    monkeypatch.setattr(settings, "DOWNLOAD_ALLOWED_DOMAINS", "tiktok.com")
    monkeypatch.setattr(settings, "REWRITE_ALLOWED_DOMAINS", "tiktok.com")
    with patch(
        "app.url_processing.follow_redirects",
        return_value="https://www.youtube.com/watch?v=abc123",
    ):
        result = await process_url_request(
            "https://www.youtube.com/watch?v=abc123", is_group_chat=False
        )
    assert "not allowed for downloading" in result
    assert "yfxtube.com" not in result


@pytest.mark.asyncio
async def test_process_url_request_youtube_falls_through_to_download_when_rewrite_disallowed(
    monkeypatch,
):
    # REWRITE_ALLOWED_DOMAINS excludes YouTube, but DOWNLOAD_ALLOWED_DOMAINS
    # is left at its permissive default — the download proceeds instead of
    # being mirrored.
    monkeypatch.setattr(settings, "REWRITE_ALLOWED_DOMAINS", "tiktok.com")
    monkeypatch.setattr(settings, "BASE_URL", "example.test")
    with (
        patch(
            "app.url_processing.follow_redirects",
            return_value="https://www.youtube.com/watch?v=abc123",
        ),
        patch(
            "app.url_processing.yt_dlp_download",
            new=AsyncMock(return_value="/cache/vid.mp4"),
        ) as mock_download,
    ):
        result = await process_url_request(
            "https://www.youtube.com/watch?v=abc123", is_group_chat=False
        )
    mock_download.assert_called_once()
    assert "example.test/vid.mp4" in result


@pytest.mark.asyncio
async def test_process_url_request_youtube_mirrored_on_download_failure():
    # Default settings: download is attempted (allowed by default) but
    # fails, so the mirror-rewrite fallback (also allowed by default) kicks
    # in.
    with (
        patch(
            "app.url_processing.follow_redirects",
            return_value="https://www.youtube.com/watch?v=abc123",
        ),
        patch(
            "app.url_processing.yt_dlp_download",
            new=AsyncMock(side_effect=UnsupportedUrlError("nope")),
        ),
    ):
        result = await process_url_request(
            "https://www.youtube.com/watch?v=abc123", is_group_chat=False
        )
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
