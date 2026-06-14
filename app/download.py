# download.py
# -*- coding: utf-8 -*-

import glob
import logging
import os
import tempfile
import yt_dlp

from app.config import settings

logger = logging.getLogger(__name__)

COOKIE_JAR_PATH = os.path.join(settings.COOKIES_DIR, "cookie_jar.txt")


class UnsupportedUrlError(Exception):
    """Custom exception for unsupported URLs"""

    pass


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


async def yt_dlp_download(url: str) -> str:
    video_path = os.path.join(settings.CACHE_DIR, f"{sanitize_subfolder_name(url)}.mp4")

    if os.path.exists(video_path):
        logger.info(f"File already exists for URL: {url}, skipping download.")
        return video_path

    try:
        ydl_opts = {
            "outtmpl": video_path,
            "format": "best",
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
        return video_path

    except yt_dlp.DownloadError as e:
        if "Unsupported URL" in str(e):
            logger.error(f"Unsupported URL: {url}")
            raise UnsupportedUrlError(f"Unsupported URL: {url}")
        else:
            logger.error(f"DownloadError for URL: {url} - {str(e)}")
            raise RuntimeError(
                f"Failed to download video from URL: {url}. Check if the URL is correct and accessible."
            ) from e

    except yt_dlp.PostProcessingError as e:
        logger.error(f"PostProcessingError for URL: {url} - {str(e)}")
        raise RuntimeError(
            f"An error occurred while processing the video file for URL: {url}."
        ) from e

    except Exception as e:
        logger.error(f"Unexpected error for URL: {url} - {str(e)}")
        raise RuntimeError(
            f"An unexpected error occurred while processing the URL: {url}. Please try again later."
        ) from e


def sanitize_subfolder_name(url: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in url)
