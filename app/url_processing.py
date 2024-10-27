# url_processing.py

import os
import logging
from urllib.parse import urlparse, urlunparse
import requests
from app.config import settings
from .download import yt_dlp_download

logger = logging.getLogger(__name__)

async def process_url_request(url: str) -> str:
    try:
        final_url = follow_redirects(url)
        if "tiktok" in final_url:
            sanitized_url = transform_tiktok_url(final_url)
        elif "youtube.com/shorts" in final_url:
            sanitized_url = final_url
        else:
            return f"Unsupported URL {final_url}"
        video_path = await yt_dlp_download(sanitized_url)
        return video_path if video_path else "Download failed"
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

def transform_tiktok_url(url: str) -> str:
    parsed_url = urlparse(url)
    return f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
