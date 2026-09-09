# cleanup.py
# -*- coding: utf-8 -*-
# UFB-0026

import logging
import os
import threading
import time

from app.config import settings
from app.pages import PREVIEW_IMAGE_FILENAME, SAMPLE_MEDIA_FILENAME, watch_page_path

logger = logging.getLogger(__name__)

_thread: threading.Thread | None = None
_stop = threading.Event()


def protected_paths() -> set[str]:
    """Absolute paths that must never be swept, regardless of age."""
    return {
        os.path.join(settings.CACHE_DIR, "index.html"),
        os.path.join(settings.CACHE_DIR, "404.html"),
        os.path.join(settings.CACHE_DIR, PREVIEW_IMAGE_FILENAME),
        os.path.join(settings.CACHE_DIR, SAMPLE_MEDIA_FILENAME),
        watch_page_path(SAMPLE_MEDIA_FILENAME),
    }


def _is_stale(path: str, ttl_seconds: float) -> bool:
    try:
        atime = os.stat(path).st_atime
    except OSError as e:
        logger.warning(f"Failed to stat {path}: {e}")
        return False
    return (time.time() - atime) > ttl_seconds


def _delete(path: str) -> bool:
    try:
        os.remove(path)
        logger.debug(f"Deleted stale cache file: {path}")
        return True
    except OSError as e:
        logger.warning(f"Failed to delete {path}: {e}")
        return False


def _watch_media_path(watch_html_path: str) -> str | None:
    """Best-effort reverse of watch_page_path: the media file a watch page
    was generated for, by stem match against CACHE_DIR's top level."""
    stem = os.path.splitext(os.path.basename(watch_html_path))[0]
    try:
        for name in os.listdir(settings.CACHE_DIR):
            if os.path.splitext(name)[0] == stem:
                return os.path.join(settings.CACHE_DIR, name)
    except OSError as e:
        logger.warning(f"Failed to list {settings.CACHE_DIR}: {e}")
    return None


def _sweep_watch_page(path: str, ttl_seconds: float) -> bool:
    """A watch page is swept once its media file is stale, or is gone."""
    media_path = _watch_media_path(path)
    stale = media_path is None or _is_stale(media_path, ttl_seconds)
    return stale and _delete(path)


def _sweep_media_file(path: str, filename: str, protected: set[str]) -> bool:
    watch_path = watch_page_path(filename)
    if watch_path not in protected and os.path.exists(watch_path):
        _delete(watch_path)
    return _delete(path)


def _prune_empty_dirs() -> None:
    for root, dirs, filenames in os.walk(settings.CACHE_DIR, topdown=False):
        if root == settings.CACHE_DIR or dirs or filenames:
            continue
        try:
            os.rmdir(root)
            logger.debug(f"Removed empty directory: {root}")
        except OSError as e:
            logger.warning(f"Failed to remove empty directory {root}: {e}")


def sweep_once() -> int:
    """Delete cache files untouched longer than FILE_TTL. Returns the number
    of files deleted."""
    ttl_seconds = settings.FILE_TTL * 86400
    protected = protected_paths()
    deleted = 0

    for root, _dirs, filenames in os.walk(settings.CACHE_DIR):
        is_watch_dir = os.path.basename(root) == "watch"
        for filename in filenames:
            path = os.path.join(root, filename)
            if path in protected:
                continue

            if is_watch_dir and filename.endswith(".html"):
                deleted += _sweep_watch_page(path, ttl_seconds)
            elif _is_stale(path, ttl_seconds):
                deleted += _sweep_media_file(path, filename, protected)

    _prune_empty_dirs()
    return deleted


def _run() -> None:
    logger.info(
        f"Cache cleanup thread started (FILE_TTL={settings.FILE_TTL}d, "
        f"CLEANUP_INTERVAL={settings.CLEANUP_INTERVAL}s)"
    )
    while not _stop.is_set():
        try:
            deleted = sweep_once()
            if deleted:
                logger.info(f"Cache cleanup deleted {deleted} stale file(s)")
        except Exception as e:
            logger.warning(f"Cache cleanup sweep failed: {e}")
        _stop.wait(settings.CLEANUP_INTERVAL)
    logger.info("Cache cleanup thread stopped")


def start_cleanup() -> None:
    """Start the cleanup thread as an observable background worker."""
    global _thread
    _stop.clear()
    _thread = threading.Thread(target=_run, name="cache-cleanup", daemon=True)
    _thread.start()


def stop_cleanup() -> None:
    """Signal the cleanup thread to stop and wait for it to exit."""
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=5)


def is_cleanup_alive() -> bool:
    return _thread is not None and _thread.is_alive()
