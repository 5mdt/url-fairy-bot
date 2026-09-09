# pages_test.py

import os

import pytest

from app import pages
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


def test_seeded_sample_page_matches_a_real_watch_page(cache_dir):
    pages.seed_static_pages()
    seeded = (cache_dir / "watch" / "sample.html").read_text(encoding="utf-8")
    direct = pages.render_watch_page(pages.SAMPLE_MEDIA_FILENAME)
    assert seeded == direct
