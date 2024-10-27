# url_processing.py
# -*- coding: utf-8 -*-

import logging
import os
from urllib.parse import urlparse, urlunparse

import requests

from app.config import settings

from .download import yt_dlp_download

logger = logging.getLogger(__name__)


async def process_url_request(url: str, is_group_chat: bool = False) -> str:
    try:
        final_url = follow_redirects(url)
        video_os_path = await yt_dlp_download(final_url)

        if video_os_path:
            # Extract the last component of the path for the video path
            video_path = os.path.join(*video_os_path.split(os.path.sep)[-1:])
            response = (
                "[Click here to ⏯️ Watch or ⏬ Download]"
                + f"(https://{settings.BASE_URL}/{video_path})\n\n"
                + f"[📎 Original]({final_url})\n"
            )
            return response
        else:
            # Define URL rewrite map
            rewrite_map = {
                "https://tiktok.com/": "https://tfxktok.com/",
                "https://twitter.com/": "https://www.fxtwitter.com/",
                "https://www.instagram.com/p/": "https://www.ddinstagram.com/p/",
                "https://www.instagram.com/reel/": "https://www.ddinstagram.com/reel/",
                "https://www.twitter.com/": "https://www.fxtwitter.com/",
                "https://x.com/": "https://www.fxtwitter.com/",
            }

            # Return None if the URL is not in the rewrite map and it’s a group chat
            if final_url == url or is_group_chat:
                if (
                    not any(
                        final_url.startswith(pattern) for pattern in rewrite_map.keys()
                    )
                    and final_url not in rewrite_map.values()
                ):
                    return None

            # Rewrite the URL for supported fallbacks
            rewritten_url = final_url
            for original, rewrite in rewrite_map.items():
                if original in final_url:
                    rewritten_url = final_url.replace(original, rewrite)
                    break

            response = (
                "I failed to download the file by myself"
                + "\n\nHere is the link,"
                + f" which Telegram parses better: [📎]({rewritten_url})"
                + f"\n[📎 Original]({final_url})\n"
            )
            return response

    except requests.exceptions.RequestException as req_e:
        logger.error(f"Request error processing URL: {req_e}")
        return None
    except Exception as e:
        logger.error(f"Error processing URL: {e}")
        return None


def follow_redirects(url: str, timeout=10) -> str:
    try:
        response = requests.head(url, allow_redirects=True, timeout=timeout)
        redirected_url = urlunparse(urlparse(response.url)._replace(query=""))

        # Validate if redirected URL is well-formed
        if not urlparse(redirected_url).scheme or not urlparse(redirected_url).netloc:
            logger.warning(f"Invalid redirect URL: {redirected_url}")
            return url  # Return original URL if redirect is invalid

        return redirected_url
    except requests.Timeout:
        logger.warning(f"Timeout for URL: {url}")
        return url
