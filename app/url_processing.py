# -*- coding: utf-8 -*-
# url_processing.py

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
        return (
            f"https://{settings.BASE_URL}{video_path}"
            if video_path
            else "Download failed"
        )
    except Exception as e:
        logger.error(f"Error processing URL: {e}")
        return str(e)


def follow_redirects(url: str, timeout=10) -> str:
    try:
        response = requests.head(url, allow_redirects=True, timeout=timeout)
        return urlunparse(urlparse(response.url)._replace(query=""))
    except requests.Timeout:
        logger.warning(f"Timeout for URL: {url}")
        return url
