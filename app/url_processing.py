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

def transform_youtube_url(url: str) -> str:
    youtube_patterns = [
        (r"^https://music\.youtube\.com/watch\?v=([a-zA-Z0-9_-]+)", r"https://music.yfxtube.com/watch?v=\1"),
        (r"^https://www\.youtube\.com/watch\?v=([a-zA-Z0-9_-]+)", r"https://www.yfxtube.com/watch?v=\1"),
        (r"^https://youtu\.be/([a-zA-Z0-9_-]+)", r"https://fxyoutu.be/\1"),
    ]
    for pattern, replacement in youtube_patterns:
        if re.match(pattern, url):
            return re.sub(pattern, replacement, url)
    return None

def apply_rewrite_map(final_url: str) -> str:
    rewrite_map = {
        r"^https://(open\.)?spotify.com": "https://fxspotify.com",
        r"^https://(www\.)?instagram\.com/p/": "https://www.ddinstagram.com/p/",
        r"^https://(www\.)?instagram\.com/reel/": "https://www.ddinstagram.com/reel/",
        r"^https://(www\.)?reddit\.com": "https://rxddit.com",
        r"^https://(www\.)?tiktok\.com": "https://tfxktok.com",
        r"^https://(www\.)?twitter\.com": "https://www.fxtwitter.com",
        r"^https://(www\.)?x\.com": "https://www.fxtwitter.com",
    }
    for pattern, replacement in rewrite_map.items():
        if re.match(pattern, final_url):
            return re.sub(pattern, replacement, final_url, count=1)
    return final_url

async def attempt_download(final_url: str) -> str:
    try:
        video_os_path = await yt_dlp_download(final_url)
        if video_os_path:
            video_path = os.path.join(*video_os_path.split(os.path.sep)[-1:])
            return f"[Click here to ⏯️ Watch or ⏬ Download](https://{settings.BASE_URL}/{video_path})\n\n[📎 Original]({final_url})"
    except UnsupportedUrlError:
        raise
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        raise UnsupportedUrlError("Download failed unexpectedly.")
    return None

async def process_url_request(url: str, is_group_chat: bool = False) -> str:
    url = str(url)  # Ensure url is a string

    # Now continue as before with the transformed url
    youtube_alternative = transform_youtube_url(url)
    if youtube_alternative:
        return (
            "YouTube video cannot be downloaded, but here’s an alternative link:"
            + f"\n\n[📎 Modified URL]({youtube_alternative})"
            + f"\n\n[📎 Original]({url})"
        )

    try:
        response = await attempt_download(url)
        if response:
            return response
    except UnsupportedUrlError:
        modified_url = apply_rewrite_map(url)
        if modified_url == url and is_group_chat:
            return None  # Silent response for unmodified URLs in group/supergroup
        return (
            "I failed to download this by myself.\n\n"
            + "Here is an alternative link, which Telegram may parse better: "
            + f"\n\n[📎 Modified URL]({modified_url})"
            + f"\n\n[📎 Original]({url})"
        )
    except Exception as e:
        logger.error(f"Unknown error processing URL: {e}")
        modified_url = apply_rewrite_map(url)
        if modified_url == url and is_group_chat:
            return None  # Silent response for unmodified URLs in group/supergroup
        return (
            "I failed to download this by myself.\n\n"
            + "Here is an alternative link, which Telegram may parse better: "
            + f"\n\n[📎 Modified URL]({modified_url})"
            + f"\n\n[📎 Original]({url})"
        )
