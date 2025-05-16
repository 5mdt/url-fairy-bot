# download.py
# -*- coding: utf-8 -*-

import glob
import logging
import os
import tempfile
import yt_dlp

from app.config import settings

logger = logging.getLogger(__name__)


class UnsupportedUrlError(Exception):
    """Custom exception for unsupported URLs"""
    pass


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


        cookie_files = glob.glob("cookies*.txt")
        if cookie_files:
            with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt") as tmp_cookie_file:
                for path in cookie_files:
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            tmp_cookie_file.write(f.read() + "\n")
                    except Exception as e:
                        logger.warning(f"Failed to read cookies file {path}: {e}")
                tmp_cookie_file.flush()
                ydl_opts["cookiefile"] = tmp_cookie_file.name
                logger.info(f"Using merged cookies from: {cookie_files}")

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
