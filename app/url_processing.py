# url_processing.py

import logging
import os
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

from app.config import settings

from .download import UnsupportedUrlError, yt_dlp_download

logger = logging.getLogger(__name__)

# Query parameters that identify the actual content (e.g. a video id) rather
# than tracking/affiliate noise. These are preserved when resolving redirects;
# everything else is stripped. See docs/features/UFB-0008-query-string-stripping.md.
CONTENT_QUERY_PARAMS = frozenset({"v", "list", "t", "index", "id"})


def _domain_in_allowlist(url: str, allowlist_csv: str) -> bool:
    """
    An empty allow-list means unrestricted (every domain matches); a
    non-empty one requires an exact or label-boundary (subdomain) match.
    """
    allowed_domains = [d.strip().lower() for d in allowlist_csv.split(",") if d.strip()]
    if not allowed_domains:
        return True

    domain = urlparse(url).netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]

    return any(
        domain == allowed_domain or domain.endswith("." + allowed_domain)
        for allowed_domain in allowed_domains
    )


def is_domain_allowed(url: str) -> bool:
    """Whether `url` may be downloaded via yt-dlp (DOWNLOAD_ALLOWED_DOMAINS)."""
    return _domain_in_allowlist(url, settings.DOWNLOAD_ALLOWED_DOMAINS)


def is_rewrite_allowed(url: str) -> bool:
    """Whether `url` may be rewritten to a mirror link (REWRITE_ALLOWED_DOMAINS)."""
    return _domain_in_allowlist(url, settings.REWRITE_ALLOWED_DOMAINS)


def follow_redirects(url: str, timeout=settings.FOLLOW_REDIRECT_TIMEOUT) -> str:
    try:
        response = requests.head(url, allow_redirects=True, timeout=timeout)
        parsed = urlparse(response.url)
        kept_params = [
            (k, v)
            for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k in CONTENT_QUERY_PARAMS
        ]
        redirected_url = urlunparse(parsed._replace(query=urlencode(kept_params)))
        if not urlparse(redirected_url).scheme or not urlparse(redirected_url).netloc:
            logger.warning(f"Invalid redirect URL: {redirected_url}")
            return url
        return redirected_url
    except requests.Timeout:
        logger.warning(f"Timeout for URL: {url} after {timeout} seconds")
        return url
    except requests.RequestException as e:
        logger.warning(f"Request error resolving redirects for URL: {url} - {e}")
        return url


def apply_rewrite_map(final_url: str) -> str:
    """
    Rewrites URLs from supported platforms to alternative mirror domains.

    If the URL matches a pattern for Spotify, Instagram, Reddit, TikTok,
    Twitter/X, or YouTube, returns the rewritten URL with the configured
    mirror domain. Otherwise (or if REWRITE_ALLOWED_DOMAINS excludes the
    domain) returns the original URL unchanged.

    Returns:
        str: The rewritten URL if a pattern matched, or the original URL
    """
    if not is_rewrite_allowed(final_url):
        return final_url

    rewrite_map = [
        (
            r"^https://(open\.)?spotify\.com",
            f"https://{settings.SPOTIFY_MIRROR_DOMAIN}",
        ),
        (
            r"^https://(www\.)?instagram\.com/p/",
            f"https://www.{settings.INSTAGRAM_MIRROR_DOMAIN}/p/",
        ),
        (
            r"^https://(www\.)?instagram\.com/reel/",
            f"https://www.{settings.INSTAGRAM_MIRROR_DOMAIN}/reel/",
        ),
        (
            r"^https://(www\.)?reddit\.com",
            f"https://{settings.REDDIT_MIRROR_DOMAIN}",
        ),
        (
            r"^https://(www\.)?tiktok\.com",
            f"https://{settings.TIKTOK_MIRROR_DOMAIN}",
        ),
        (
            r"^https://(www\.)?twitter\.com",
            f"https://www.{settings.TWITTER_MIRROR_DOMAIN}",
        ),
        (
            r"^https://(www\.)?x\.com",
            f"https://www.{settings.TWITTER_MIRROR_DOMAIN}",
        ),
        (
            r"^https://music\.youtube\.com/watch\?v=([a-zA-Z0-9_-]+)",
            rf"https://music.{settings.YOUTUBE_MIRROR_DOMAIN}/watch?v=\1",
        ),
        (
            r"^https://(?:www\.|m\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)",
            rf"https://www.{settings.YOUTUBE_MIRROR_DOMAIN}/watch?v=\1",
        ),
        (
            r"^https://(?:www\.|m\.)?youtube\.com/shorts/([a-zA-Z0-9_-]+)",
            rf"https://www.{settings.YOUTUBE_MIRROR_DOMAIN}/shorts/\1",
        ),
        (
            r"^https://youtu\.be/([a-zA-Z0-9_-]+)",
            rf"https://{settings.YOUTUBE_SHORT_MIRROR_DOMAIN}/\1",
        ),
    ]
    for pattern, replacement in rewrite_map:
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
