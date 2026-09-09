# cleanup_test.py

import os
import time

import pytest

from app import cleanup, pages
from app.config import settings


def _age(path: str, days: float) -> None:
    """Set both atime and mtime `days` days into the past."""
    stamp = time.time() - days * 86400
    os.utime(path, (stamp, stamp))


def _touch_recent(path: str, mtime_days: float = 0) -> None:
    """Recent atime, but an old mtime — the case #BUG-0046 got wrong."""
    now = time.time()
    os.utime(path, (now, now - mtime_days * 86400))


@pytest.fixture(autouse=True)
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "FILE_TTL", 3)
    return tmp_path


# --- sweep_once: TTL by access time ---


def test_untouched_file_past_ttl_is_deleted(cache_dir):
    f = cache_dir / "stale.mp4"
    f.write_text("data")
    _age(str(f), days=10)

    cleanup.sweep_once()

    assert not f.exists()


def test_recently_touched_file_with_old_mtime_is_kept(cache_dir):
    f = cache_dir / "still_read.mp4"
    f.write_text("data")
    _touch_recent(str(f), mtime_days=30)

    cleanup.sweep_once()

    assert f.exists()


def test_fresh_file_is_kept(cache_dir):
    f = cache_dir / "fresh.mp4"
    f.write_text("data")

    cleanup.sweep_once()

    assert f.exists()


# --- watch page pairing ---


def test_deleting_stale_media_also_deletes_its_watch_page(cache_dir):
    media = cache_dir / "video.mp4"
    media.write_text("data")
    _age(str(media), days=10)

    watch_path = pages.watch_page_path("video.mp4")
    os.makedirs(os.path.dirname(watch_path), exist_ok=True)
    with open(watch_path, "w") as fh:
        fh.write("<html></html>")
    _age(watch_path, days=10)

    cleanup.sweep_once()

    assert not media.exists()
    assert not os.path.exists(watch_path)


def test_orphaned_watch_page_without_media_is_deleted(cache_dir):
    watch_path = pages.watch_page_path("gone.mp4")
    os.makedirs(os.path.dirname(watch_path), exist_ok=True)
    with open(watch_path, "w") as fh:
        fh.write("<html></html>")
    _age(watch_path, days=10)

    cleanup.sweep_once()

    assert not os.path.exists(watch_path)


# --- seeded pages are exempt ---


def test_seeded_pages_are_never_deleted_even_when_ancient(cache_dir):
    pages.seed_static_pages()

    for path in (
        os.path.join(str(cache_dir), "index.html"),
        os.path.join(str(cache_dir), "404.html"),
        os.path.join(str(cache_dir), pages.PREVIEW_IMAGE_FILENAME),
        os.path.join(str(cache_dir), pages.SAMPLE_MEDIA_FILENAME),
        pages.watch_page_path(pages.SAMPLE_MEDIA_FILENAME),
    ):
        _age(path, days=3650)

    cleanup.sweep_once()

    for path in (
        os.path.join(str(cache_dir), "index.html"),
        os.path.join(str(cache_dir), "404.html"),
        os.path.join(str(cache_dir), pages.PREVIEW_IMAGE_FILENAME),
        os.path.join(str(cache_dir), pages.SAMPLE_MEDIA_FILENAME),
        pages.watch_page_path(pages.SAMPLE_MEDIA_FILENAME),
    ):
        assert os.path.exists(path)


# --- empty directory pruning ---


def test_empty_directory_left_after_deletion_is_pruned(cache_dir):
    sub = cache_dir / "watch"
    sub.mkdir()
    f = sub / "video.html"
    f.write_text("data")
    _age(str(f), days=10)

    cleanup.sweep_once()

    assert not sub.exists()


def test_cache_dir_itself_is_never_removed(cache_dir):
    cleanup.sweep_once()
    assert cache_dir.exists()


# --- thread lifecycle ---


def test_start_and_stop_cleanup_toggles_liveness(monkeypatch):
    monkeypatch.setattr(settings, "CLEANUP_INTERVAL", 3600)
    assert cleanup.is_cleanup_alive() is False

    cleanup.start_cleanup()
    try:
        assert cleanup.is_cleanup_alive() is True
    finally:
        cleanup.stop_cleanup()

    assert cleanup.is_cleanup_alive() is False
