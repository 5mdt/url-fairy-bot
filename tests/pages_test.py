# pages_test.py

import os
from unittest.mock import patch

import pytest

from app import pages, preview
from app.config import settings


@pytest.fixture(autouse=True)
def cache_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    return tmp_path


# --- watch_page_path / watch_page_url ---


def test_watch_page_path_maps_media_filename_to_watch_subdir(cache_dir):
    assert pages.watch_page_path("x.mp4") == str(cache_dir / "watch" / "x.html")


def test_watch_page_url_maps_media_filename_to_html_url():
    assert pages.watch_page_url("x.mp4") == "https://example.test/watch/x.html"


def test_watch_page_url_percent_encodes_the_stem():
    url = pages.watch_page_url("some video (1).mp4")
    assert url == "https://example.test/watch/some%20video%20%281%29.html"


# --- render_watch_page ---


def test_render_watch_page_contains_required_meta_tags():
    html = pages.render_watch_page("clip.mp4")

    assert 'property="og:type" content="video.other"' in html
    assert 'property="og:title"' in html
    assert 'property="og:url" content="https://example.test/watch/clip.html"' in html
    assert 'property="og:video" content="https://example.test/clip.mp4"' in html
    assert (
        'property="og:video:secure_url" content="https://example.test/clip.mp4"' in html
    )
    assert 'property="og:video:type" content="video/mp4"' in html
    assert 'property="og:image" content="https://example.test/preview.png"' in html
    assert 'name="twitter:card" content="player"' in html
    assert (
        'name="twitter:player:stream" content="https://example.test/clip.mp4"' in html
    )
    assert 'src="https://example.test/clip.mp4"' in html


def test_render_watch_page_escapes_filename_metacharacters():
    html = pages.render_watch_page('a"b&c.mp4')
    assert "a%22b%26c.mp4" in html
    assert '"b&c' not in html


def test_render_watch_page_uses_per_file_preview_when_present(cache_dir):
    preview_path = preview.preview_path("clip.mp4")
    os.makedirs(os.path.dirname(preview_path), exist_ok=True)
    with open(preview_path, "wb") as f:
        f.write(b"fake jpeg data")

    html = pages.render_watch_page("clip.mp4")

    assert 'property="og:image" content="https://example.test/preview/clip.jpg"' in html
    assert "https://example.test/preview.png" not in html


def test_render_watch_page_falls_back_to_bundled_preview_when_absent(cache_dir):
    html = pages.render_watch_page("clip.mp4")
    assert 'property="og:image" content="https://example.test/preview.png"' in html


def test_render_watch_page_derives_video_type_from_real_extension():
    html = pages.render_watch_page("clip.webm")
    assert 'property="og:video:type" content="video/webm"' in html


def test_render_watch_page_keeps_inline_video_at_or_under_threshold(cache_dir):
    with open(cache_dir / "clip.mp4", "wb") as f:
        f.write(b"0" * (settings.INLINE_VIDEO_MAX_MB * 1024 * 1024))

    html = pages.render_watch_page("clip.mp4")

    assert 'property="og:video"' in html
    assert 'name="twitter:card" content="player"' in html
    assert "<video" in html
    assert "<p><video" not in html


def test_render_watch_page_drops_inline_video_over_threshold(cache_dir):
    with open(cache_dir / "clip.mp4", "wb") as f:
        f.write(b"0" * (settings.INLINE_VIDEO_MAX_MB * 1024 * 1024 + 1))

    html = pages.render_watch_page("clip.mp4")

    assert 'property="og:video"' not in html
    assert 'name="twitter:card"' not in html
    assert "<video" not in html
    assert 'property="og:image"' in html
    assert 'href="https://example.test/clip.mp4"' in html


def test_render_watch_page_treats_missing_media_file_as_small(cache_dir):
    html = pages.render_watch_page("missing.mp4")
    assert 'property="og:video"' in html


# --- write_watch_page ---


def test_write_watch_page_creates_watch_dir(cache_dir):
    path = pages.write_watch_page("clip.mp4")
    assert os.path.isfile(path)
    assert (cache_dir / "watch" / "clip.html").read_text(encoding="utf-8") == open(
        path, encoding="utf-8"
    ).read()


def test_write_watch_page_overwrites_existing_page(cache_dir):
    watch_dir = cache_dir / "watch"
    watch_dir.mkdir()
    (watch_dir / "clip.html").write_text("stale", encoding="utf-8")

    pages.write_watch_page("clip.mp4")

    content = (watch_dir / "clip.html").read_text(encoding="utf-8")
    assert content != "stale"
    assert "clip.mp4" in content


def test_write_watch_page_leaves_no_tmp_file(cache_dir):
    pages.write_watch_page("clip.mp4")
    assert list((cache_dir / "watch").glob("*.tmp")) == []


# --- seed_static_pages ---


def test_seed_static_pages_writes_every_permanent_page(cache_dir):
    pages.seed_static_pages()

    assert (cache_dir / "index.html").is_file()
    assert (cache_dir / "404.html").is_file()
    assert (cache_dir / pages.PREVIEW_IMAGE_FILENAME).is_file()
    assert (cache_dir / pages.SAMPLE_MEDIA_FILENAME).is_file()
    assert (cache_dir / "watch" / "sample.html").is_file()


def test_seed_static_pages_is_idempotent(cache_dir):
    pages.seed_static_pages()
    pages.seed_static_pages()

    assert (cache_dir / "watch" / "sample.html").is_file()


def test_seed_static_pages_landing_page_has_no_cache_listing_link(cache_dir):
    pages.seed_static_pages()
    content = (cache_dir / "index.html").read_text(encoding="utf-8")
    assert "/cache/" not in content


def test_seed_static_pages_generates_a_preview_for_the_sample_clip(cache_dir):
    with patch("app.pages.preview.generate_preview") as mock_generate:
        pages.seed_static_pages()

    mock_generate.assert_called_once_with(
        str(cache_dir / pages.SAMPLE_MEDIA_FILENAME)
    )


def test_seed_static_pages_survives_preview_generation_failure(cache_dir):
    with patch("app.pages.preview.generate_preview", side_effect=OSError("boom")):
        pages.seed_static_pages()

    assert (cache_dir / "watch" / "sample.html").is_file()


def test_seeded_sample_page_matches_a_real_watch_page(cache_dir):
    pages.seed_static_pages()
    seeded = (cache_dir / "watch" / "sample.html").read_text(encoding="utf-8")
    direct = pages.render_watch_page(pages.SAMPLE_MEDIA_FILENAME)
    assert seeded == direct


def test_seed_static_pages_regenerates_watch_pages_for_pre_existing_media(cache_dir):
    with open(cache_dir / "clip.mp4", "wb") as f:
        f.write(b"fake video data")
    watch_dir = cache_dir / "watch"
    watch_dir.mkdir()
    (watch_dir / "clip.html").write_text("stale", encoding="utf-8")

    pages.seed_static_pages()

    content = (watch_dir / "clip.html").read_text(encoding="utf-8")
    assert content != "stale"
    assert "clip.mp4" in content


def test_seed_static_pages_skips_a_file_that_fails_to_regenerate(cache_dir):
    with open(cache_dir / "clip.mp4", "wb") as f:
        f.write(b"fake video data")

    real_write_watch_page = pages.write_watch_page

    def _raise_only_for_clip(media_filename):
        if media_filename == "clip.mp4":
            raise OSError("boom")
        return real_write_watch_page(media_filename)

    with patch("app.pages.write_watch_page", side_effect=_raise_only_for_clip):
        pages.seed_static_pages()  # doesn't raise

    assert (cache_dir / "watch" / "sample.html").is_file()
