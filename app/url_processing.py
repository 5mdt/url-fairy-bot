# url_processing.py
import logging
import os
import re
from urllib.parse import urlparse, urlunparse

import requests

from app.config import settings

from .download import UnsupportedUrlError, yt_dlp_download

logger = logging.getLogger(__name__)


def follow_redirects(url: str, timeout=settings.FOLLOW_REDIRECT_TIMEOUT) -> str:
    try:
        response = requests.head(url, allow_redirects=True, timeout=timeout)
        redirected_url = urlunparse(urlparse(response.url)._replace(query=""))

        if not urlparse(redirected_url).scheme or not urlparse(redirected_url).netloc:
            logger.warning(f"Invalid redirect URL: {redirected_url}")
            return url

        return redirected_url
    except requests.Timeout:
        logger.warning(f"Timeout for URL: {url} after {timeout} seconds")
        return url


rewrite_map = {
    r"^https://(www\.)?tiktok\.com": "https://tfxktok.com",
    r"^https://(www\.)?twitter\.com": "https://www.fxtwitter.com",
    r"^https://(www\.)?x\.com": "https://www.fxtwitter.com",
    r"^https://(www\.)?instagram\.com/p/": "https://www.ddinstagram.com/p/",
    r"^https://(www\.)?instagram\.com/reel/": "https://www.ddinstagram.com/reel/",
}


async def process_url_request(url: str, is_group_chat: bool = False) -> str:
    url = str(url)
    final_url = url  # Keep the original URL as a fallback

    # Check for specific YouTube patterns to transform without downloading
    youtube_patterns = [
        (
            r"^https://www\.youtube\.com/watch\?v=([a-zA-Z0-9_-]+)",
            r"https://www.yfxtube.com/watch?v=\1",
        ),
        (r"^https://youtu\.be/([a-zA-Z0-9_-]+)", r"https://fxyoutu.be/\1"),
    ]

    for pattern, replacement in youtube_patterns:
        if re.match(pattern, url):
            modified_url = re.sub(pattern, replacement, url)
            return (
                "YouTube video cannot be downloaded, but here’s an alternative link:"
                + f"\n\n[📎 Modified URL]({modified_url})"
                + f"\n\n[📎 Original]({url})"
            )

    try:
        # Attempt to follow redirects and download video content
        final_url = follow_redirects(url)
        video_os_path = await yt_dlp_download(final_url)

        if video_os_path:
            video_path = os.path.join(*video_os_path.split(os.path.sep)[-1:])
            response = (
                "[Click here to ⏯️ Watch or ⏬ Download]"
                + f"(https://{settings.BASE_URL}/{video_path})"
                + f"\n\n[📎 Original]({final_url})"
            )
            return response
        else:
            raise UnsupportedUrlError

    except UnsupportedUrlError:

        modified_url = final_url
        for pattern, replacement in rewrite_map.items():
            if re.match(pattern, final_url):
                modified_url = re.sub(pattern, replacement, final_url, count=1)
                logger.info(f"Rewrite applied for URL: {final_url} -> {modified_url}")
                break

        response = (
            "I failed to download the file by myself."
            + "Here is an alternative link, which Telegram may parse better: "
            + f"\n\n[📎 Modified URL]({modified_url})"
            + f"\n\n[📎 Original]({final_url})"
        )
        return response

    except Exception as e:
        logger.error(f"Error processing URL: {e}")
        # Default to modified/original link display if an unknown error occurs
        modified_url = final_url
        for pattern, replacement in rewrite_map.items():
            if re.match(pattern, final_url):
                modified_url = re.sub(pattern, replacement, final_url, count=1)
                break
        return (
            "I failed to download the file by myself.\n\n"
            + "Here is an alternative link, which Telegram may parse better: "
            + f"\n\n[📎 Modified URL]({modified_url})"
            + f"\n\n[📎 Original]({final_url})"
        )
