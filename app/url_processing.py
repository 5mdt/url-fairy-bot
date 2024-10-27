# url_processing.py
# -*- coding: utf-8 -*-

import logging
from urllib.parse import urlparse, urlunparse

import requests

from app.config import settings

from .download import yt_dlp_download

logger = logging.getLogger(__name__)


async def process_url_request(url: str) -> str:
    try:
        final_url = follow_redirects(url)
        if "youtube.com/shorts" in final_url:
            sanitized_url = final_url
        elif "tiktok" in final_url:
            sanitized_url = final_url
        else:
            return f"Unsupported URL {final_url}"

        video_path = await yt_dlp_download(sanitized_url)

        if video_path:
            return (
                "[Click here to ⏯️ Watch or ⏬ Download]"
                + f"(https://{settings.BASE_URL}{video_path})\n\n"
                + f"[📎 Original]({final_url})\n"
            )
        else:
            rewritten_url = final_url.replace("tiktok.com/", "tfxktok.com/")
            return (
                "I failed to download the file by myself"
                + "\n\nHere is the link,"
                + f" which Telegram parses better: [📎]({rewritten_url})"
                + f"\n[📎 Original]({final_url})\n"
            )

    except requests.exceptions.RequestException as req_e:
        logger.error(f"Request error processing URL: {req_e}")
        return f"Request error: {str(req_e)}"
    except Exception as e:
        logger.error(f"Error processing URL: {e}")
        return f"An error occurred: {str(e)}"


def follow_redirects(url: str, timeout=10) -> str:
    try:
        response = requests.head(url, allow_redirects=True, timeout=timeout)
        return urlunparse(urlparse(response.url)._replace(query=""))
    except requests.Timeout:
        logger.warning(f"Timeout for URL: {url}")
        return url
