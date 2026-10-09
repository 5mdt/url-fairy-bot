# url_processing.py

import asyncio
import ipaddress
import logging
import os
import re
import shutil
import socket
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import (
    parse_qsl,
    quote,
    urlencode,
    urljoin,
    urlparse,
    urlunparse,
)

import requests

from app.config import settings

from . import messages, metadata, metrics, pages, preview, reddit, reports
from .download import (
    UnsupportedUrlError,
    is_tiktok_photo_url,
    tiktok_gallery_download,
    url_to_filename_stem,
    yt_dlp_download,
)

logger = logging.getLogger(__name__)


# #UFB-0036, #UFB-0039
@dataclass
class DownloadResult:
    """A successful download's reply text, plus the on-disk media path so
    the bot can also try a native video reply (UFB-0036). Every other
    process_url_request outcome (mirror-link fallback, error message,
    silent group-chat response) stays a plain str/None — only a real
    download carries a media_path."""

    text: str
    media_path: str | None
    # #UFB-0039: a photo post's images; `media_path` is then its audio (or None).
    image_paths: list[str] = field(default_factory=list)


# Query parameters that identify the actual content (e.g. a video id) rather
# than tracking/affiliate noise. These are preserved when resolving redirects;
# everything else is stripped.
# #UFB-0008
CONTENT_QUERY_PARAMS = frozenset({"v", "list", "t", "index", "id"})


# Platforms yt-dlp has no extractor for; downloading is pointless (#BUG-0032).
# #UFB-0011
NO_DOWNLOAD_DOMAINS = ("spotify.com",)


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


# #UFB-0007, #BUG-0012
class BlockedUrlError(ValueError):
    """A URL (or a redirect hop) points at a non-public address or scheme."""


# #UFB-0007, #BUG-0012
MAX_REDIRECT_HOPS = 10
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


# #UFB-0007, #BUG-0012
def _is_public_ip(raw: str) -> bool:
    ip = ipaddress.ip_address(raw.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
        or not ip.is_global
    )


# #UFB-0007, #BUG-0012
def _assert_public_url(url: str) -> None:
    """Raise BlockedUrlError unless `url` is http(s) and every address its
    host resolves to is public. An unresolvable host passes: the request
    that follows fails and callers fall back as before (#UFB-0007)."""
    parsed = urlparse(url)
    host = parsed.hostname
    if parsed.scheme not in ("http", "https") or not host:
        raise BlockedUrlError("URL scheme or host not allowed")
    try:
        infos = socket.getaddrinfo(host, parsed.port or None, proto=socket.IPPROTO_TCP)
    except socket.gaierror, UnicodeError:
        return
    for info in infos:
        if not _is_public_ip(info[4][0]):
            logger.warning(f"Blocked non-public target: {url}")
            raise BlockedUrlError("URL target not allowed")


# #UFB-0007, #UFB-0008, #BUG-0012
def follow_redirects(url: str, timeout=settings.FOLLOW_REDIRECT_TIMEOUT) -> str:
    try:
        current = url
        for _ in range(MAX_REDIRECT_HOPS + 1):
            _assert_public_url(current)
            response = requests.head(current, allow_redirects=False, timeout=timeout)
            location = response.headers.get("Location")
            if response.status_code not in _REDIRECT_STATUSES or not location:
                break
            current = urljoin(current, location)
            if (
                urlparse(current).scheme in ("http", "https")
                and not urlparse(current).netloc
            ):
                logger.warning(f"Invalid redirect URL: {current}")
                return url
        else:
            logger.warning(f"Too many redirects for URL: {url}")
            return url
        parsed = urlparse(current)
        kept_params = [
            (k, v)
            for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k in CONTENT_QUERY_PARAMS
        ]
        redirected = parsed._replace(query=urlencode(kept_params))
        redirected_url = urlunparse(redirected)
        if not redirected.scheme or not redirected.netloc:
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
    # Instagram is deliberately scoped to /p/ and /reel/ (unlike the
    # domain-wide entries): the mirror only serves posts and reels, so
    # profile/story links would break if rewritten (#BUG-0031).
    for pattern, replacement in rewrite_map:
        if re.match(pattern, final_url):
            return re.sub(pattern, replacement, final_url, count=1)
    return final_url


# #UFB-0039
def _iv_watch_url(page_url: str) -> str:
    return (
        f"https://t.me/iv?url={quote(page_url, safe='')}&rhash={settings.IV_RHASH}"
        if settings.IV_RHASH
        else page_url
    )


# Telegram's caption limit; the reply text is the caption of a native video.
_CAPTION_LIMIT = 1024
# Telegram's text message limit (#UFB-0057: a Reddit reply with no media).
_MESSAGE_LIMIT = 4096


# #UFB-0041
def _download_text(
    watch_url: str, source_url: str, record: dict | None, more_url: str | None = None
) -> str:
    """The reply text: the short metadata block (when a record exists and
    fits) above the links, always under Telegram's caption limit."""
    links = messages.download_result(watch_url, source_url)
    # Budget counts markup and escapes, so it is conservative; 2 = the blank line.
    meta = metadata.caption(record, _CAPTION_LIMIT - 1 - len(links) - 2, more_url)
    if not meta:
        return links
    return messages.download_result(watch_url, source_url, meta=meta)


# #UFB-0039, #UFB-0041
async def _attempt_gallery_download(final_url: str) -> DownloadResult:
    gallery = await tiktok_gallery_download(final_url)
    watch_url = final_url
    more_url = None
    if gallery.audio_path:
        audio_name = os.path.basename(gallery.audio_path)
        # The first image stands in as the audio's preview image.
        try:
            dest = preview.preview_path(audio_name)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copyfile(gallery.image_paths[0], dest)
        except OSError as e:
            logger.warning(f"Failed to write gallery preview for {audio_name}: {e}")
        try:
            pages.write_watch_page(
                audio_name,
                [pages.gallery_image_url(audio_name, p) for p in gallery.image_paths],
            )
        except OSError as e:
            logger.error(f"Failed to write watch page for {audio_name}: {e}")
        page_url = pages.watch_page_url(audio_name)
        watch_url = _iv_watch_url(page_url)
        more_url = _iv_watch_url(f"{page_url}#description")
    text = _download_text(watch_url, final_url, metadata.lookup(final_url), more_url)
    return DownloadResult(
        text=text, media_path=gallery.audio_path, image_paths=gallery.image_paths
    )


# #UFB-0015, #UFB-0032, #UFB-0033, #UFB-0035, #UFB-0036, #UFB-0041, #UFB-0057
async def _video_result(final_url: str, video_os_path: str) -> DownloadResult:
    video_path = os.path.basename(video_os_path)
    try:
        # #BUG-0006: ffmpeg runs off the event loop
        await asyncio.to_thread(preview.generate_preview, video_os_path)
    except OSError as e:
        logger.warning(f"Failed to generate preview for {video_path}: {e}")
    try:
        pages.write_watch_page(video_path)
    except OSError as e:
        logger.error(f"Failed to write watch page for {video_path}: {e}")
    page_url = pages.watch_page_url(video_path)
    watch_url = _iv_watch_url(page_url)
    text = _download_text(
        watch_url,
        final_url,
        metadata.read(video_path),
        _iv_watch_url(f"{page_url}#description"),
    )
    return DownloadResult(text=text, media_path=video_os_path)


# #UFB-0057
_REDDIT_IV_LABELS = {
    "comment": "📄 Original post",
    "profile": "📄 Profile",
    "subreddit": "📄 Subreddit",
}


# #UFB-0057
def _reddit_text(
    source_url: str,
    record: dict,
    limit: int,
    iv_url: str = "",
    iv_label: str = "",
    more_url: str | None = None,
) -> str:
    """The Reddit reply: metadata block above the links, within `limit`."""
    links = messages.reddit_result(source_url, iv_url=iv_url, iv_label=iv_label)
    meta = metadata.caption(
        record,
        limit - 1 - len(links) - 2,
        more_url,
        long_excerpt=limit > _CAPTION_LIMIT,
    )
    if not meta:
        return links
    return messages.reddit_result(
        source_url, meta=meta, iv_url=iv_url, iv_label=iv_label
    )


# #UFB-0057
async def _attempt_reddit(final_url: str) -> DownloadResult:
    download = await reddit.reddit_download(final_url)
    if download.video_path:
        return await _video_result(final_url, download.video_path)
    page_url = pages.reddit_page_url(url_to_filename_stem(final_url))
    kind = download.record.get("reddit")
    if kind == "post":
        # A post links its page only when the text is clipped.
        text = _reddit_text(
            final_url,
            download.record,
            _CAPTION_LIMIT if download.image_paths else _MESSAGE_LIMIT,
            more_url=_iv_watch_url(f"{page_url}#description"),
        )
    else:
        text = _reddit_text(
            final_url,
            download.record,
            _CAPTION_LIMIT if download.image_paths else _MESSAGE_LIMIT,
            iv_url=_iv_watch_url(page_url),
            iv_label=_REDDIT_IV_LABELS.get(kind, "📄 Instant View"),
        )
    return DownloadResult(text=text, media_path=None, image_paths=download.image_paths)


# #UFB-0015, #UFB-0032, #UFB-0033, #UFB-0035, #UFB-0036, #UFB-0039, #UFB-0041, #UFB-0057
async def attempt_download(final_url: str) -> DownloadResult | None:
    try:
        if reddit.parse_link(final_url):
            return await _attempt_reddit(final_url)
        if is_tiktok_photo_url(final_url):
            return await _attempt_gallery_download(final_url)
        video_os_path = await yt_dlp_download(final_url)
        if video_os_path:
            return await _video_result(final_url, video_os_path)
    except UnsupportedUrlError:
        raise
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        raise UnsupportedUrlError("Download failed unexpectedly.")
    return None


# #UFB-0004, #UFB-0007, #UFB-0009, #UFB-0010, #UFB-0011, #UFB-0013, #UFB-0014, #UFB-0045, #UFB-0051, #UFB-0055
async def process_url_request(
    url: str,
    is_group_chat: bool = False,
    on_download: Callable[[], None] | None = None,
) -> str | DownloadResult | None:
    url = str(url)  # Ensure url is a string

    # Follow redirects first to get the final URL
    # #BUG-0006: blocking requests.head, kept off the event loop
    final_url = await asyncio.to_thread(follow_redirects, url)

    platform = metrics.platform_for(final_url)  # #UFB-0045
    metrics.record_request(platform)

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
        if _domain_in_allowlist(final_url, ",".join(NO_DOWNLOAD_DOMAINS)):
            raise UnsupportedUrlError("Known non-video platform.")
        if on_download:
            on_download()  # #UFB-0055: a reply is coming; show progress
        with metrics.timed(metrics.observe_download, platform):
            try:
                response = await attempt_download(final_url)
            except UnsupportedUrlError:
                metrics.record_download_outcome(platform, "failure")
                raise
        if response:
            metrics.record_download_outcome(platform, "success")
            return response
        metrics.record_download_outcome(platform, "failure")
    except UnsupportedUrlError:
        modified_url = apply_rewrite_map(final_url)
        if modified_url != final_url:
            metrics.record_download_outcome(platform, "fallback_mirror")

        # Check if modified URL is the same as the original
        if modified_url == final_url and is_group_chat:
            return None  # Silent response for unmodified URLs in group/supergroup

        if modified_url == final_url:
            return reports.FailureReply(
                messages.download_failed(final_url), final_url, "failure"
            )  # #UFB-0051

        return reports.FailureReply(  # #UFB-0051
            messages.download_failed_mirror(modified_url, final_url),
            final_url,
            "fallback_mirror",
        )
