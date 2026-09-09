# download.py
# -*- coding: utf-8 -*-

import glob
import logging
import os
import tempfile
import time

import yt_dlp

from app.config import settings

logger = logging.getLogger(__name__)

COOKIE_JAR_PATH = os.path.join(settings.COOKIES_DIR, "cookie_jar.txt")


# #UFB-0013
class UnsupportedUrlError(Exception):
    """Custom exception for unsupported URLs"""

    pass


# #UFB-0017
def _write_merged_cookies(dest: str, cookie_files: list[str]) -> None:
    with open(dest, "w", encoding="utf-8") as out:
        out.write("# Netscape HTTP Cookie File\n")
        for path in cookie_files:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.startswith("# ") and line.strip() != "#":
                            out.write(line)
            except Exception as e:
                logger.warning(f"Failed to read cookies file {path}: {e}")


# #UFB-0017, #UFB-0018
def _resolve_cookie_path(cookie_files: list[str]) -> tuple[str, bool]:
    """Returns (cookie_file_path, should_delete_after)."""
    if settings.COOKIE_JAR_ENABLED:
        if not os.path.exists(COOKIE_JAR_PATH):
            logger.info(f"Initializing cookie jar from: {cookie_files}")
            _write_merged_cookies(COOKIE_JAR_PATH, cookie_files)
        else:
            logger.info(f"Using existing cookie jar: {COOKIE_JAR_PATH}")
        return COOKIE_JAR_PATH, False

    tmp = tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".txt", encoding="utf-8"
    )
    tmp.close()
    _write_merged_cookies(tmp.name, cookie_files)
    logger.info(f"Using merged temp cookies from: {cookie_files}")
    return tmp.name, True


# #UFB-0026
def _touch_atime(path: str) -> None:
    """Mark a cache hit as a touch so it isn't swept as stale."""
    try:
        st = os.stat(path)
        os.utime(path, (time.time(), st.st_mtime))
    except OSError as e:
        logger.warning(f"Failed to refresh atime for {path}: {e}")


# Leftover fragments from an interrupted yt-dlp download; never a finished file.
_INCOMPLETE_SUFFIXES = (".part", ".ytdl")


# #UFB-0015
def _cached_media_path(stem: str) -> str | None:
    """The cached media file for `stem`, at whatever real extension it was
    actually saved with (#BUG-0015: no longer assumed to be `.mp4`), or
    None if nothing finished downloading for it yet."""
    for match in glob.glob(os.path.join(settings.CACHE_DIR, f"{stem}.*")):
        if not match.endswith(_INCOMPLETE_SUFFIXES):
            return match
    return None


# #UFB-0015, #UFB-0016, #UFB-0017
async def yt_dlp_download(url: str) -> str:
    stem = sanitize_subfolder_name(url)
    cached_path = _cached_media_path(stem)

    if cached_path:
        logger.info(f"File already exists for URL: {url}, skipping download.")
        _touch_atime(cached_path)
        return cached_path

    try:
        ydl_opts = {
            "outtmpl": os.path.join(settings.CACHE_DIR, f"{stem}.%(ext)s"),
            "format": "best",
            # Losslessly repackage a compatible non-mp4 container into a
            # real .mp4 instead of leaving the file mislabeled (#BUG-0015).
            "merge_output_format": "mp4",
            "postprocessors": [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}],
        }

        cookie_files = glob.glob(os.path.join(settings.COOKIES_DIR, "cookies*.txt"))
        if cookie_files:
            cookie_path, should_delete = _resolve_cookie_path(cookie_files)
            ydl_opts["cookiefile"] = cookie_path
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            finally:
                if should_delete:
                    try:
                        os.unlink(cookie_path)
                    except Exception:
                        pass
        else:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        logger.info(f"Download successful for URL: {url}")
        return _cached_media_path(stem)

    except yt_dlp.DownloadError as e:
        if "Unsupported URL" in str(e):
            logger.error(f"Unsupported URL: {url}")
            raise UnsupportedUrlError(f"Unsupported URL: {url}")
        else:
            logger.error(f"DownloadError for URL: {url} - {str(e)}")
            raise RuntimeError(
                f"Failed to download video from URL: {url}. Check if the URL is correct and accessible."
            ) from e

    except yt_dlp.utils.PostProcessingError as e:
        logger.error(f"PostProcessingError for URL: {url} - {str(e)}")
        raise RuntimeError(
            f"An error occurred while processing the video file for URL: {url}."
        ) from e

    except Exception as e:
        logger.error(f"Unexpected error for URL: {url} - {str(e)}")
        raise RuntimeError(
            f"An unexpected error occurred while processing the URL: {url}. Please try again later."
        ) from e


# #UFB-0016
def sanitize_subfolder_name(url: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in url)
