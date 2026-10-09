# cleanup.py
# -*- coding: utf-8 -*-
# #UFB-0026

import logging
import os
import threading
import time

from app import duplicates, metadata
from app.config import settings
from app.pages import PREVIEW_IMAGE_FILENAME, SAMPLE_MEDIA_FILENAME, watch_page_path
from app.preview import preview_path

logger = logging.getLogger(__name__)

_thread: threading.Thread | None = None
_stop = threading.Event()


# #UFB-0026, #UFB-0035
def protected_paths() -> set[str]:
    """Absolute paths that must never be swept, regardless of age."""
    return {
        os.path.join(settings.CACHE_DIR, "index.html"),
        os.path.join(settings.CACHE_DIR, "404.html"),
        os.path.join(settings.CACHE_DIR, PREVIEW_IMAGE_FILENAME),
        os.path.join(settings.CACHE_DIR, SAMPLE_MEDIA_FILENAME),
        watch_page_path(SAMPLE_MEDIA_FILENAME),
        preview_path(SAMPLE_MEDIA_FILENAME),
    }


# #UFB-0026
def _is_stale(path: str, ttl_seconds: float) -> bool:
    try:
        atime = os.stat(path).st_atime
    except OSError as e:
        logger.warning(f"Failed to stat {path}: {e}")
        return False
    return (time.time() - atime) > ttl_seconds


# #UFB-0026
def _delete(path: str) -> bool:
    try:
        os.remove(path)
        logger.debug(f"Deleted stale cache file: {path}")
        return True
    except OSError as e:
        logger.warning(f"Failed to delete {path}: {e}")
        return False


# #UFB-0026, #UFB-0035
def _sibling_media_path(sibling_path: str) -> str | None:
    """Best-effort reverse of watch_page_path/preview_path: the media file
    a watch page or preview image was generated for, by stem match against
    CACHE_DIR's top level."""
    stem = os.path.splitext(os.path.basename(sibling_path))[0]
    try:
        for name in os.listdir(settings.CACHE_DIR):
            if os.path.splitext(name)[0] == stem:
                return os.path.join(settings.CACHE_DIR, name)
    except OSError as e:
        logger.warning(f"Failed to list {settings.CACHE_DIR}: {e}")
    return None


# #UFB-0026
def _sweep_watch_page(path: str, ttl_seconds: float) -> bool:
    """A watch page is swept once its media file is stale, or is gone."""
    media_path = _sibling_media_path(path)
    stale = media_path is None or _is_stale(media_path, ttl_seconds)
    return stale and _delete(path)


# #UFB-0035
def _sweep_preview_image(path: str, ttl_seconds: float) -> bool:
    """A preview image is swept once its media file is stale, or is gone."""
    media_path = _sibling_media_path(path)
    stale = media_path is None or _is_stale(media_path, ttl_seconds)
    return stale and _delete(path)


# #UFB-0041
def _media_exists(stem: str) -> bool:
    """Whether media for `stem` is still cached: a top-level file, or a
    photo gallery directory (a post without audio has no top-level file)."""
    if os.path.isdir(os.path.join(settings.CACHE_DIR, "gallery", stem)):
        return True
    if os.path.exists(os.path.join(settings.CACHE_DIR, "reddit", f"{stem}.html")):
        return True  # #UFB-0057: a text-only Reddit post has only its page
    try:
        return any(
            os.path.splitext(name)[0] == stem
            and os.path.isfile(os.path.join(settings.CACHE_DIR, name))
            for name in os.listdir(settings.CACHE_DIR)
        )
    except OSError as e:
        logger.warning(f"Failed to list {settings.CACHE_DIR}: {e}")
        return True  # unknown: keep it


# #UFB-0041
def _sweep_orphan_sidecar(path: str, stem: str) -> bool:
    """A metadata record or subtitle file is swept only once its media is
    gone, so it never disappears from a still-served watch page."""
    return not _media_exists(stem) and _delete(path)


# #UFB-0041
def _delete_subtitles(filename: str) -> None:
    subs = metadata.subs_dir(filename)
    try:
        names = os.listdir(subs)
    except OSError:
        return
    for name in names:
        _delete(os.path.join(subs, name))


# #UFB-0026, #UFB-0035, #UFB-0041
def _sweep_media_file(path: str, filename: str, protected: set[str]) -> bool:
    watch_path = watch_page_path(filename)
    if watch_path not in protected and os.path.exists(watch_path):
        _delete(watch_path)
    preview_file = preview_path(filename)
    if preview_file not in protected and os.path.exists(preview_file):
        _delete(preview_file)
    metadata.delete(filename)
    _delete_subtitles(filename)
    return _delete(path)


# #UFB-0026
def _prune_empty_dirs() -> None:
    for root, dirs, filenames in os.walk(settings.CACHE_DIR, topdown=False):
        if root == settings.CACHE_DIR or dirs or filenames:
            continue
        try:
            os.rmdir(root)
            logger.debug(f"Removed empty directory: {root}")
        except OSError as e:
            logger.warning(f"Failed to remove empty directory {root}: {e}")


# #UFB-0026, #UFB-0035, #UFB-0041, #UFB-0050
def sweep_once() -> int:
    """Delete cache files untouched longer than FILE_TTL. Returns the number
    of files deleted."""
    ttl_seconds = settings.FILE_TTL * 86400
    protected = protected_paths()
    meta_root = os.path.join(settings.CACHE_DIR, "meta")
    subs_root = os.path.join(settings.CACHE_DIR, "subs")
    replies_root = duplicates.replies_dir()
    deleted = 0

    for root, _dirs, filenames in os.walk(settings.CACHE_DIR):
        dirname = os.path.basename(root)
        is_watch_dir = dirname == "watch"
        is_preview_dir = dirname == "preview"
        for filename in filenames:
            path = os.path.join(root, filename)
            if path in protected:
                continue

            if root == replies_root:  # #UFB-0050
                deleted += duplicates.sweep_file(path)
            elif root == meta_root:
                stem = filename.split(".", 1)[0]
                deleted += _sweep_orphan_sidecar(path, stem)
            elif os.path.dirname(root) == subs_root:
                deleted += _sweep_orphan_sidecar(path, os.path.basename(root))
            elif is_watch_dir and filename.endswith(".html"):
                deleted += _sweep_watch_page(path, ttl_seconds)
            elif is_preview_dir and filename.endswith(".jpg"):
                deleted += _sweep_preview_image(path, ttl_seconds)
            elif _is_stale(path, ttl_seconds):
                deleted += _sweep_media_file(path, filename, protected)

    _prune_empty_dirs()
    return deleted


# #UFB-0026
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


# #UFB-0026
def start_cleanup() -> None:
    """Start the cleanup thread as an observable background worker."""
    global _thread
    _stop.clear()
    _thread = threading.Thread(target=_run, name="cache-cleanup", daemon=True)
    _thread.start()


# #UFB-0026
def stop_cleanup() -> None:
    """Signal the cleanup thread to stop and wait for it to exit."""
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=5)


# #UFB-0026, #UFB-0034
def is_cleanup_alive() -> bool:
    return _thread is not None and _thread.is_alive()
