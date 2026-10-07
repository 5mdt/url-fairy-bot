# url_processing_test.py

from unittest.mock import AsyncMock, patch

import pytest
import requests

from app.config import settings
from app.download import UnsupportedUrlError
from app.url_processing import (
    BlockedUrlError,
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
            "https://www.threads.com/@user/post/abc123",
            "https://fx.akitsuki.me/@user/post/abc123",
        ),
        (
            "https://threads.com/@user/post/abc123",
            "https://fx.akitsuki.me/@user/post/abc123",
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
    monkeypatch.setattr(settings, "THREADS_MIRROR_DOMAIN", "threads.mirror.example")
    monkeypatch.setattr(settings, "TWITTER_MIRROR_DOMAIN", "twitter.mirror.example")
    monkeypatch.setattr(settings, "YOUTUBE_MIRROR_DOMAIN", "yt.mirror.example")
    monkeypatch.setattr(settings, "YOUTUBE_SHORT_MIRROR_DOMAIN", "yt.short.example")

    assert (
        apply_rewrite_map("https://open.spotify.com/track/abc")
        == "https://spotify.mirror.example/track/abc"
    )
    assert (
        apply_rewrite_map("https://www.threads.com/@user/post/abc123")
        == "https://threads.mirror.example/@user/post/abc123"
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


def _resp(status=200, location=None):
    headers = {"Location": location} if location else {}
    return type("R", (), {"status_code": status, "headers": headers})()


def _resolver(mapping):
    """getaddrinfo stand-in: host -> list of IP strings."""

    def fake(host, port, *args, **kwargs):
        return [(2, 1, 6, "", (ip, 0)) for ip in mapping[host]]

    return fake


# #UFB-0007, #UFB-0008
def test_follow_redirects_resolves_and_strips_query():
    responses = [
        _resp(301, "https://final.example.com/path?foo=bar"),
        _resp(200),
    ]
    with patch("requests.head", side_effect=responses):
        assert follow_redirects("https://short.example.com/x") == (
            "https://final.example.com/path"
        )


# #UFB-0007
def test_follow_redirects_returns_original_on_timeout():
    with patch("requests.head", side_effect=requests.Timeout):
        assert (
            follow_redirects("https://slow.example.com/x")
            == "https://slow.example.com/x"
        )


# #UFB-0007
def test_follow_redirects_returns_original_on_invalid_redirect_target():
    responses = [_resp(302, "http://")]
    with patch("requests.head", side_effect=responses):
        assert (
            follow_redirects("https://short.example.com/x")
            == "https://short.example.com/x"
        )


# #UFB-0008
def test_follow_redirects_preserves_query_string():
    responses = [_resp(302, "https://www.youtube.com/watch?v=abc123"), _resp(200)]
    with patch("requests.head", side_effect=responses):
        assert follow_redirects("https://short.example.com/x") == (
            "https://www.youtube.com/watch?v=abc123"
        )


# #UFB-0007
def test_follow_redirects_handles_connection_error():
    with patch("requests.head", side_effect=requests.ConnectionError):
        assert follow_redirects("https://unreachable.example.com/x") == (
            "https://unreachable.example.com/x"
        )


# #UFB-0007
def test_follow_redirects_disables_automatic_redirects():
    with patch("requests.head", return_value=_resp(200)) as head:
        follow_redirects("https://a.example.com/x")
    assert head.call_args.kwargs["allow_redirects"] is False


# #UFB-0007
def test_follow_redirects_resolves_relative_location():
    responses = [_resp(301, "/final?v=1&utm=2"), _resp(200)]
    with patch("requests.head", side_effect=responses):
        assert follow_redirects("https://a.example.com/x") == (
            "https://a.example.com/final?v=1"
        )


# #UFB-0007
def test_follow_redirects_hop_limit_falls_back_to_original():
    with patch("requests.head", return_value=_resp(302, "/loop")):
        assert follow_redirects("https://a.example.com/x") == (
            "https://a.example.com/x"
        )


# #BUG-0012
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/x",
        "http://localhost/x",
        "http://10.0.0.5/x",
        "http://192.168.1.1/x",
        "http://172.16.0.1/x",
        "http://169.254.169.254/latest/meta-data/",
        "http://0.0.0.0/x",
        "http://[::1]/x",
        "http://[::ffff:127.0.0.1]/x",
        "http://[fe80::1]/x",
        "http://224.0.0.1/x",
        "http://240.0.0.1/x",
    ],
)
def test_follow_redirects_blocks_non_public_targets(url):
    with patch("app.url_processing.socket.getaddrinfo", side_effect=_real_literal):
        with patch("requests.head") as head:
            with pytest.raises(BlockedUrlError):
                follow_redirects(url)
    head.assert_not_called()


def _real_literal(host, port, *args, **kwargs):
    import ipaddress

    host = "127.0.0.1" if host == "localhost" else host
    ip = ipaddress.ip_address(host)
    return [(2, 1, 6, "", (str(ip), 0))]


# #BUG-0012
def test_follow_redirects_blocks_hostname_resolving_to_private():
    resolver = _resolver({"internal.example.com": ["10.1.2.3"]})
    with patch("app.url_processing.socket.getaddrinfo", side_effect=resolver):
        with patch("requests.head") as head:
            with pytest.raises(BlockedUrlError):
                follow_redirects("https://internal.example.com/x")
    head.assert_not_called()


# #BUG-0012
def test_follow_redirects_blocks_mixed_public_and_private_answers():
    resolver = _resolver({"mixed.example.com": ["93.184.216.34", "127.0.0.1"]})
    with patch("app.url_processing.socket.getaddrinfo", side_effect=resolver):
        with pytest.raises(BlockedUrlError):
            follow_redirects("https://mixed.example.com/x")


# #BUG-0012
def test_follow_redirects_blocks_redirect_hop_to_private_host():
    resolver = _resolver(
        {
            "public.example.com": ["93.184.216.34"],
            "evil.example.com": ["169.254.169.254"],
        }
    )
    responses = [_resp(302, "http://evil.example.com/meta"), _resp(200)]
    with patch("app.url_processing.socket.getaddrinfo", side_effect=resolver):
        with patch("requests.head", side_effect=responses) as head:
            with pytest.raises(BlockedUrlError):
                follow_redirects("https://public.example.com/x")
    assert head.call_count == 1


# #BUG-0012
def test_follow_redirects_blocks_non_http_hop():
    with patch("requests.head", return_value=_resp(302, "file:///etc/passwd")):
        with pytest.raises(BlockedUrlError):
            follow_redirects("https://public.example.com/x")


# #BUG-0012
def test_follow_redirects_unresolvable_host_falls_back_to_original():
    import socket

    with (
        patch("app.url_processing.socket.getaddrinfo", side_effect=socket.gaierror),
        patch("requests.head", side_effect=requests.ConnectionError),
    ):
        assert follow_redirects("https://nx.example.com/x") == (
            "https://nx.example.com/x"
        )


# --- apply_rewrite_map: security case (BUGS.md #22) ---


def test_apply_rewrite_map_does_not_match_spoofed_spotify_domain():
    url = "https://spotifyXcom.evil.tld/track/abc"
    assert apply_rewrite_map(url) == url


def test_apply_rewrite_map_does_not_match_spoofed_threads_domain():
    url = "https://threadsXcom.evil.tld/@user/post/abc"
    assert apply_rewrite_map(url) == url


# --- attempt_download ---


@pytest.mark.asyncio
async def test_attempt_download_success(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "BASE_URL", "example.test")
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    with patch(
        "app.url_processing.yt_dlp_download",
        new=AsyncMock(return_value="/cache/some_video.mp4"),
    ):
        result = await attempt_download("https://tiktok.com/@user/video/1")

    assert "https://example.test/watch/some_video.html" in result.text
    assert "https://tiktok.com/@user/video/1" in result.text
    assert result.media_path == "/cache/some_video.mp4"
    assert (tmp_path / "watch" / "some_video.html").exists()


@pytest.mark.asyncio
async def test_attempt_download_percent_encodes_watch_page_url(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "BASE_URL", "example.test")
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    with patch(
        "app.url_processing.yt_dlp_download",
        new=AsyncMock(return_value="/cache/some video (1).mp4"),
    ):
        result = await attempt_download("https://tiktok.com/@user/video/1")

    assert "https://example.test/watch/some%20video%20%281%29.html" in result.text


@pytest.mark.asyncio
async def test_attempt_download_uses_instant_view_link_when_rhash_set(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "BASE_URL", "example.test")
    monkeypatch.setattr(settings, "IV_RHASH", "abc123")
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    with patch(
        "app.url_processing.yt_dlp_download",
        new=AsyncMock(return_value="/cache/some_video.mp4"),
    ):
        result = await attempt_download("https://tiktok.com/@user/video/1")

    expected_page_url = "https%3A%2F%2Fexample.test%2Fwatch%2Fsome_video.html"
    # `&` is HTML-escaped to `&amp;` inside the rendered <a href="..."> — the
    # reply is now HTML (UFB-0014/UFB-0037), not Markdown.
    assert f"https://t.me/iv?url={expected_page_url}&amp;rhash=abc123" in result.text
    assert "https://tiktok.com/@user/video/1" in result.text


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
    assert '<a href="https://example.com/x">' in result


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
    assert "can be parsed better" in result
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
async def test_process_url_request_disallowed_download_allows_everything_by_default(
    monkeypatch, tmp_path
):
    # Default (empty) DOWNLOAD_ALLOWED_DOMAINS means every domain is allowed
    # for download — a real download is attempted rather than a mirror
    # offered.
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
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
    assert "vid.html" in result.text
    assert result.media_path == "/cache/vid.mp4"


@pytest.mark.asyncio
async def test_process_url_request_youtube_downloads_by_default(monkeypatch, tmp_path):
    # YouTube is no longer special-cased: with the default (empty)
    # DOWNLOAD_ALLOWED_DOMAINS, a YouTube URL is downloaded like any other
    # platform rather than mirrored.
    monkeypatch.setattr(settings, "BASE_URL", "example.test")
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
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
    assert "example.test/watch/vid.html" in result.text


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
    assert "can be parsed better" in result
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
    monkeypatch, tmp_path
):
    # REWRITE_ALLOWED_DOMAINS excludes YouTube, but DOWNLOAD_ALLOWED_DOMAINS
    # is left at its permissive default — the download proceeds instead of
    # being mirrored.
    monkeypatch.setattr(settings, "REWRITE_ALLOWED_DOMAINS", "tiktok.com")
    monkeypatch.setattr(settings, "BASE_URL", "example.test")
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
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
    assert "example.test/watch/vid.html" in result.text


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
async def test_process_url_request_allowed_download_succeeds(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DOWNLOAD_ALLOWED_DOMAINS", "tiktok.com")
    monkeypatch.setattr(settings, "BASE_URL", "example.test")
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
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
    assert "example.test/watch/vid.html" in result.text
    assert result.media_path == "/cache/vid.mp4"


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


# #UFB-0013, #BUG-0033
@pytest.mark.asyncio
async def test_process_url_request_download_failed_no_rewrite_private_states_failure(
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
        result = await process_url_request("https://example.com/x", is_group_chat=False)
    assert "parsed better" not in result
    assert "cannot download" in result
    assert 'href="https://example.com/x"' in result


# #UFB-0011, #BUG-0032
@pytest.mark.asyncio
async def test_process_url_request_skips_yt_dlp_for_spotify(monkeypatch):
    monkeypatch.setattr(settings, "DOWNLOAD_ALLOWED_DOMAINS", "spotify.com")
    url = "https://open.spotify.com/track/abc"
    with (
        patch("app.url_processing.follow_redirects", return_value=url),
        patch("app.url_processing.yt_dlp_download", new=AsyncMock()) as mock_dl,
    ):
        result = await process_url_request(url, is_group_chat=False)

    mock_dl.assert_not_called()
    assert "fxspotify.com" in result


# --- UFB-0039: TikTok photo galleries ---


@pytest.mark.asyncio
async def test_attempt_download_routes_photo_url_to_gallery(tmp_path, monkeypatch):
    from app.download import GalleryDownload

    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "BASE_URL", "example.test")
    image = tmp_path / "01.jpg"
    image.write_bytes(b"jpg")
    audio = tmp_path / "post.mp3"
    audio.write_bytes(b"mp3")
    gallery = GalleryDownload(audio_path=str(audio), image_paths=[str(image)])
    with (
        patch(
            "app.url_processing.tiktok_gallery_download",
            new=AsyncMock(return_value=gallery),
        ),
        patch("app.url_processing.yt_dlp_download", new=AsyncMock()) as mock_video,
    ):
        result = await attempt_download("https://www.tiktok.com/@u/photo/1")

    mock_video.assert_not_awaited()
    assert result.image_paths == [str(image)]
    assert result.media_path == str(audio)
    assert "example.test/watch/post.html" in result.text
    assert (tmp_path / "preview" / "post.jpg").read_bytes() == b"jpg"
    page = (tmp_path / "watch" / "post.html").read_text(encoding="utf-8")
    assert "<audio" in page
    assert "og:video" not in page
    assert 'src="https://example.test/gallery/post/01.jpg"' in page


@pytest.mark.asyncio
async def test_attempt_download_gallery_without_audio_links_source_only(
    tmp_path, monkeypatch
):
    from app.download import GalleryDownload

    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    gallery = GalleryDownload(audio_path=None, image_paths=["/x/01.jpg"])
    with patch(
        "app.url_processing.tiktok_gallery_download",
        new=AsyncMock(return_value=gallery),
    ):
        result = await attempt_download("https://www.tiktok.com/@u/photo/1")
    assert result.media_path is None
    assert result.text.count("https://www.tiktok.com/@u/photo/1") == 2


# --- UFB-0041: metadata in the reply caption ---


# #UFB-0041
@pytest.mark.asyncio
async def test_attempt_download_caption_includes_metadata(monkeypatch, tmp_path):
    from app import metadata

    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    metadata.write(
        "some_video",
        {"title": "Cool <clip>", "uploader": "Bob", "description": "About it"},
    )
    with patch(
        "app.url_processing.yt_dlp_download",
        new=AsyncMock(return_value="/cache/some_video.mp4"),
    ):
        result = await attempt_download("https://tiktok.com/@user/video/1")

    assert result.text.startswith("<b>Cool &lt;clip&gt;</b>\nBob\n<i>About it</i>\n\n")
    assert "https://example.test/watch/some_video.html" in result.text
    assert "Cool" in (tmp_path / "watch" / "some_video.html").read_text()


# #UFB-0041
@pytest.mark.asyncio
async def test_attempt_download_caption_stays_under_telegram_limit(
    monkeypatch, tmp_path
):
    from app import metadata

    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "IV_RHASH", "abcdef123456")
    metadata.write(
        "some_video",
        {"title": "T&" * 400, "uploader": "U<" * 400, "description": "D&" * 5000},
    )
    long_url = "https://tiktok.com/@user/video/1?" + "a=b&" * 50
    with patch(
        "app.url_processing.yt_dlp_download",
        new=AsyncMock(return_value="/cache/some_video.mp4"),
    ):
        result = await attempt_download(long_url)

    assert len(result.text) < 1024


# #UFB-0041
@pytest.mark.asyncio
async def test_attempt_download_without_metadata_replies_as_before(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    with patch(
        "app.url_processing.yt_dlp_download",
        new=AsyncMock(return_value="/cache/some_video.mp4"),
    ):
        result = await attempt_download("https://tiktok.com/@user/video/1")

    assert result.text.startswith("<a ")


# #UFB-0041, #UFB-0039
@pytest.mark.asyncio
async def test_attempt_download_gallery_caption_includes_metadata(
    tmp_path, monkeypatch
):
    from app import metadata
    from app.download import GalleryDownload, url_to_filename_stem

    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    url = "https://www.tiktok.com/@u/photo/1"
    metadata.write(url_to_filename_stem(url), {"title": "Photos", "uploader": "Nick"})
    gallery = GalleryDownload(audio_path=None, image_paths=["/x/01.jpg"])
    with patch(
        "app.url_processing.tiktok_gallery_download",
        new=AsyncMock(return_value=gallery),
    ):
        result = await attempt_download(url)

    assert result.text.startswith("<b>Photos</b>\nNick\n\n")
