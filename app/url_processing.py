# url_processing.py

import logging
import os
import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

import requests

from app.config import settings

from . import messages, pages, preview
from .download import UnsupportedUrlError, yt_dlp_download

logger = logging.getLogger(__name__)


# #UFB-0036
@dataclass
class DownloadResult:
    """A successful download's reply text, plus the on-disk media path so
    the bot can also try a native video reply (UFB-0036). Every other
    process_url_request outcome (mirror-link fallback, error message,
    silent group-chat response) stays a plain str/None — only a real
    download carries a media_path."""

    text: str
    media_path: str


# Query parameters that identify the actual content (e.g. a video id) rather
# than tracking/affiliate noise. These are preserved when resolving redirects;
# everything else is stripped.
# #UFB-0008
CONTENT_QUERY_PARAMS = frozenset({"v", "list", "t", "index", "id"})


# #UFB-0009, #UFB-0023
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


# #UFB-0009
def is_domain_allowed(url: str) -> bool:
    """Whether `url` may be downloaded via yt-dlp (DOWNLOAD_ALLOWED_DOMAINS)."""
    return _domain_in_allowlist(url, settings.DOWNLOAD_ALLOWED_DOMAINS)


# #UFB-0023
def is_rewrite_allowed(url: str) -> bool:
    """Whether `url` may be rewritten to a mirror link (REWRITE_ALLOWED_DOMAINS)."""
    return _domain_in_allowlist(url, settings.REWRITE_ALLOWED_DOMAINS)


# #UFB-0007, #UFB-0008
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


# #UFB-0010, #UFB-0011, #UFB-0012, #UFB-0022, #UFB-0023, #UFB-0029
def apply_rewrite_map(final_url: str) -> str:
    """
    Rewrites URLs from supported platforms to alternative mirror domains.

    If the URL matches a pattern for Spotify, Instagram, Reddit, Threads,
    TikTok, Twitter/X, or YouTube, returns the rewritten URL with the configured
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
            r"^https://(www\.)?threads\.com",
            f"https://{settings.THREADS_MIRROR_DOMAIN}",
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


# #UFB-0015, #UFB-0032, #UFB-0033, #UFB-0035, #UFB-0036
async def attempt_download(final_url: str) -> DownloadResult | None:
    try:
        video_os_path = await yt_dlp_download(final_url)
        if video_os_path:
            video_path = os.path.join(*video_os_path.split(os.path.sep)[-1:])
            try:
                preview.generate_preview(video_os_path)
            except OSError as e:
                logger.warning(f"Failed to generate preview for {video_path}: {e}")
            try:
                pages.write_watch_page(video_path)
            except OSError as e:
                logger.error(f"Failed to write watch page for {video_path}: {e}")
            page_url = pages.watch_page_url(video_path)
            watch_url = (
                f"https://t.me/iv?url={quote(page_url, safe='')}&rhash={settings.IV_RHASH}"
                if settings.IV_RHASH
                else page_url
            )
            text = messages.download_result(watch_url, final_url)
            return DownloadResult(text=text, media_path=video_os_path)
    except UnsupportedUrlError:
        raise
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        raise UnsupportedUrlError("Download failed unexpectedly.")
    return None


# #UFB-0004, #UFB-0007, #UFB-0009, #UFB-0010, #UFB-0013, #UFB-0014
async def process_url_request(
    url: str, is_group_chat: bool = False
) -> str | DownloadResult | None:
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
            return messages.domain_not_allowed(final_url)

        return messages.domain_not_allowed_with_mirror(modified_url, final_url)

    try:
        response = await attempt_download(final_url)
        if response:
            return response
    except UnsupportedUrlError:
        modified_url = apply_rewrite_map(final_url)

        # Check if modified URL is the same as the original
        if modified_url == final_url and is_group_chat:
            return None  # Silent response for unmodified URLs in group/supergroup

        return messages.download_failed_mirror(modified_url, final_url)
