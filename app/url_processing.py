# url_processing.py

import logging
import os
import re
from urllib.parse import urlparse, urlunparse

import requests

from app.config import settings

from .download import UnsupportedUrlError, yt_dlp_download

logger = logging.getLogger(__name__)


def is_domain_allowed(url: str) -> bool:
    allowed_domains = (
        settings.DOWNLOAD_ALLOWED_DOMAINS.split(",")
        if settings.DOWNLOAD_ALLOWED_DOMAINS
        else []
    )
    domain = urlparse(url).netloc

    # Normalize the domain by stripping 'www.' if present for comparison
    domain = domain.lower()
    if domain.startswith("www."):
        domain = domain[4:]

    # Check for exact match or subdomain match
    for allowed_domain in allowed_domains:
        if domain.endswith(allowed_domain.lower()):
            return True

    return False


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
        (
            r"^https://music\.youtube\.com/watch\?v=([a-zA-Z0-9_-]+)",
            r"https://music.yfxtube.com/watch?v=\1",
        ),
        (
            r"^https://www\.youtube\.com/watch\?v=([a-zA-Z0-9_-]+)",
            r"https://www.yfxtube.com/watch?v=\1",
        ),
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
            return f"[⏯️ Watch or ⏬ Download](https://{settings.BASE_URL}/{video_path})\n\n[📎]({final_url})"
    except UnsupportedUrlError:
        raise
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        raise UnsupportedUrlError("Download failed unexpectedly.")
    return None


async def process_url_request(url: str, is_group_chat: bool = False) -> str:
    url = str(url)  # Ensure url is a string

    # Follow redirects first to get the final URL
    final_url = follow_redirects(url)

    # Check if the domain is allowed
    if not is_domain_allowed(final_url):
        # If domain is not allowed, skip downloading and provide a modified URL
        modified_url = apply_rewrite_map(final_url)

        # If the original and modified URL are the same, don't include the modified URL in the response
        if modified_url == final_url:
            # Stay silent in group chats when the URLs are identical
            if is_group_chat:
                return None
            return (
                "This domain is not allowed for downloading. "
                + f"\n\n[📎 Original]({final_url})"
            )

        return (
            "This domain is not allowed for downloading, but here's an alternative link:"
            + f"\n\n[📎 Modified URL]({modified_url})"
            + f"\n\n[📎 Original]({final_url})"
        )

    youtube_alternative = transform_youtube_url(final_url)
    if youtube_alternative:
        return (
            "YouTube video cannot be downloaded, but here’s an alternative link:"
            + f"\n\n[📎 Modified URL]({youtube_alternative})"
            + f"\n\n[📎 Original]({final_url})"
        )

    try:
        response = await attempt_download(final_url)
        if response:
            return response
    except UnsupportedUrlError:
        modified_url = apply_rewrite_map(final_url)

        # Check if modified URL is the same as the original
        if modified_url == final_url and is_group_chat:
            return None  # Silent response for unmodified URLs in group/supergroup

        return (
            "Here is an alternative link, which Telegram may parse better: "
            + f"\n\n[📎 Modified URL]({modified_url})"
            + f"\n\n[📎]({final_url})"
        )
    except Exception as e:
        logger.error(f"Unknown error processing URL: {e}")
        modified_url = apply_rewrite_map(final_url)

        # Check if modified URL is the same as the original
        if modified_url == final_url and is_group_chat:
            return None  # Silent response for unmodified URLs in group/supergroup

        return (
            "Here is an alternative link, which Telegram may parse better: "
            + f"\n\n[📎 Modified URL]({modified_url})"
            + f"\n\n[📎 Original]({final_url})"
        )
