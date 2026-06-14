# url_processing_test.py

import pytest

from app.config import settings
from app.url_processing import apply_rewrite_map, transform_youtube_url

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
