# reddit.py
# -*- coding: utf-8 -*-
# #UFB-0057: Reddit posts, comments, profiles and subreddits, read through
# Reddit's API (anonymous access is blocked): app-only OAuth, else the
# reddit.com cookies, else anonymous.

import asyncio
import glob
import http.cookiejar
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import quote, urlparse

import requests

from app import download, metadata, metrics, pages
from app.config import settings
from app.download import (
    UnsupportedUrlError,
    _cached_media_path,
    _touch_atime,
    _url_lock,
    _write_atomic_bytes,
    url_to_filename_stem,
    yt_dlp_download,
)

logger = logging.getLogger(__name__)

_TIMEOUT = 15
# Telegram's sendPhoto limit; a bigger image falls back to its preview.
_MAX_IMAGE_BYTES = 10 * 1024 * 1024
_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


# #UFB-0057
class RedditError(UnsupportedUrlError):
    """Reddit refused or returned nothing usable; the caller falls back to
    the mirror link (#UFB-0013)."""


# --- links ---


# #UFB-0057
@dataclass(frozen=True)
class RedditLink:
    kind: str  # post | comment | profile | subreddit
    name: str | None = None  # subreddit or user name
    post_id: str | None = None
    comment_id: str | None = None


_HOST_RE = re.compile(r"^(?:www\.|old\.|new\.|m\.|np\.)?reddit\.com$", re.I)
_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


# #UFB-0057
def _thread_link(rest: list[str], name: str | None) -> RedditLink | None:
    """`rest` starts at `comments`: comments/<id>[/<slug>[/<comment id>]] or
    comments/<id>/comment/<comment id>."""
    if len(rest) < 2 or not _NAME_RE.match(rest[1]):
        return None
    post_id = rest[1]
    comment_id = None
    if len(rest) >= 4 and rest[2] == "comment":
        comment_id = rest[3]
    elif len(rest) >= 4:
        comment_id = rest[3]
    if comment_id is not None and not _NAME_RE.match(comment_id):
        return None
    return RedditLink(
        "comment" if comment_id else "post",
        name=name,
        post_id=post_id,
        comment_id=comment_id,
    )


# #UFB-0057
def parse_link(url: str) -> RedditLink | None:
    """What a Reddit URL points at, or None for anything else (wiki, search,
    unresolved share links)."""
    try:
        parsed = urlparse(str(url))
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not _HOST_RE.match(
        parsed.hostname or ""
    ):
        return None
    segs = [s for s in parsed.path.split("/") if s]
    if not segs:
        return None
    head = segs[0].lower()
    if head == "comments":
        return _thread_link(segs, None)
    if head not in ("r", "user", "u") or len(segs) < 2 or not _NAME_RE.match(segs[1]):
        return None
    name, rest = segs[1], segs[2:]
    if rest and rest[0] == "comments":
        return _thread_link(rest, name)
    if head == "r":
        return RedditLink("subreddit", name=name) if rest in ([], ["about"]) else None
    return RedditLink("profile", name=name) if rest in ([], ["overview"]) else None


# --- API ---

_TOKEN = {"value": None, "expires": 0.0}
_TOKEN_LOCK = threading.Lock()


# #UFB-0057
def reset_token() -> None:
    with _TOKEN_LOCK:
        _TOKEN.update(value=None, expires=0.0)


# #UFB-0057
def _headers() -> dict:
    return {"User-Agent": settings.REDDIT_USER_AGENT}


# #UFB-0057
def _token(force: bool = False) -> str:
    with _TOKEN_LOCK:
        if not force and _TOKEN["value"] and time.time() < _TOKEN["expires"]:
            return _TOKEN["value"]
        response = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(settings.REDDIT_CLIENT_ID, settings.REDDIT_CLIENT_SECRET),
            data={"grant_type": "client_credentials"},
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        try:
            body = response.json()
        except ValueError:
            body = None
        token = body.get("access_token") if isinstance(body, dict) else None
        if response.status_code != 200 or not token:
            raise RedditError(f"Reddit token request failed ({response.status_code})")
        expires_in = body.get("expires_in")
        ttl = expires_in if isinstance(expires_in, (int, float)) else 3600
        _TOKEN.update(value=token, expires=time.time() + max(ttl - 60, 0))
        return token


# #UFB-0057
def _read_cookies(path: str) -> dict[str, str]:
    jar = http.cookiejar.MozillaCookieJar()
    jar.load(path, ignore_discard=True, ignore_expires=True)
    found = {}
    for cookie in jar:
        domain = cookie.domain.lstrip(".")
        if domain == "reddit.com" or domain.endswith(".reddit.com"):
            found[cookie.name] = cookie.value
    return found


# #UFB-0038, #UFB-0057
def _cookies() -> dict[str, str]:
    """reddit.com cookies: from the cookie jar when it is enabled, so the
    keepalive's refreshed values are used (read without the jar lock, which
    a download can hold for minutes); else, or if the jar is missing or
    unreadable, from COOKIES_DIR/cookies*.txt."""
    if settings.COOKIE_JAR_ENABLED and os.path.exists(download.COOKIE_JAR_PATH):
        try:
            return _read_cookies(download.COOKIE_JAR_PATH)
        except (OSError, http.cookiejar.LoadError) as e:
            logger.warning(f"Failed to read the cookie jar, using cookie files: {e}")
    found: dict[str, str] = {}
    for path in sorted(glob.glob(os.path.join(settings.COOKIES_DIR, "cookies*.txt"))):
        try:
            found.update(_read_cookies(path))
        except (OSError, http.cookiejar.LoadError) as e:
            logger.warning(f"Failed to read cookies file {path}: {e}")
    return found


# #UFB-0057
def _oauth_get(path: str, params: dict) -> requests.Response:
    for attempt in (0, 1):
        response = requests.get(
            f"https://oauth.reddit.com{path}",
            params=params,
            headers={
                **_headers(),
                "Authorization": f"bearer {_token(force=attempt == 1)}",
            },
            timeout=_TIMEOUT,
        )
        if response.status_code != 401:
            break
    return response


# #UFB-0057
def _api_get(path: str, **params):
    """The JSON for an API `path` (blocking). Anything but a clean answer
    raises RedditError."""
    params = {**params, "raw_json": 1}
    try:
        if settings.REDDIT_CLIENT_ID and settings.REDDIT_CLIENT_SECRET:
            response = _oauth_get(path, params)
        else:
            response = requests.get(
                f"https://www.reddit.com{path}.json",
                params=params,
                headers=_headers(),
                cookies=_cookies(),
                timeout=_TIMEOUT,
            )
    except requests.RequestException as e:
        raise RedditError(f"Reddit request failed: {e}") from e
    if response.status_code != 200:
        raise RedditError(f"Reddit answered {response.status_code} for {path}")
    try:
        body = response.json()
    except ValueError as e:
        raise RedditError(f"Reddit sent non-JSON for {path}") from e
    if isinstance(body, dict) and "error" in body:
        raise RedditError(
            f"Reddit error for {path}: {body.get('reason') or body['error']}"
        )
    return body


# --- reading the API's data ---


# #UFB-0057
@dataclass
class _Img:
    key: str
    url: str
    fallback: str | None = None
    album: bool = True  # sent in the Telegram album, not only on the page
    filename: str | None = None


# #UFB-0057
@dataclass
class _Section:
    title: str | None = None
    heading: str | None = None
    author: str | None = None
    author_url: str | None = None
    subreddit: str | None = None
    subreddit_url: str | None = None
    subtitle: str | None = None
    body: str = ""
    images: list[_Img] = field(default_factory=list)
    avatar: _Img | None = None


# #UFB-0057
@dataclass
class _Fetched:
    kind: str
    record: dict
    page_title: str
    sections: list[_Section]
    banner: _Img | None = None
    hls_url: str | None = None


# #UFB-0057
@dataclass
class RedditDownload:
    """`record` is the stored metadata record; `image_paths` the album;
    `video_path` the cached video of a video post (then there is no page)."""

    record: dict
    image_paths: list[str]
    video_path: str | None = None


# #UFB-0057
def _s(value) -> str:
    return value.strip() if isinstance(value, str) else ""


# #UFB-0057
def _date(timestamp) -> str:
    if not isinstance(timestamp, (int, float)):
        return ""
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d")


# #UFB-0057
def _count(value) -> str:
    return f"{value:,}" if isinstance(value, int) else ""


# #UFB-0057
def _https(url) -> str | None:
    url = _s(url)
    return url if url.startswith("https://") else None


_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_MARKER_RE = re.compile(r"\s*\[\[img:[^\]]+\]\]\s*")


# #UFB-0057
def _inline(text: str, media_metadata: dict) -> tuple[str, list[str]]:
    """Reddit's `![img](id)` image syntax becomes a `[[img:id]]` paragraph;
    the ids come back in order of appearance."""
    ids: list[str] = []

    def replace(match: re.Match) -> str:
        key = match.group(1)
        if key not in media_metadata:
            return ""
        ids.append(key)
        return f"\n\n[[img:{key}]]\n\n"

    text = _MD_IMAGE_RE.sub(replace, text or "")
    return re.sub(r"\n{3,}", "\n\n", text).strip(), ids


# #UFB-0057
def _plain(text: str) -> str:
    return _MARKER_RE.sub("\n\n", text).strip()


# #UFB-0057
def _meta_urls(entry) -> tuple[str, str | None] | None:
    """(url, fallback) of a `media_metadata` entry; an animated image is its
    largest still, since Telegram photos cannot move."""
    if not isinstance(entry, dict) or entry.get("status") != "valid":
        return None
    previews = entry.get("p") if isinstance(entry.get("p"), list) else []
    preview = _https(previews[-1].get("u")) if previews else None
    if entry.get("e") == "AnimatedImage":
        return (preview, None) if preview else None
    full = _https((entry.get("s") or {}).get("u"))
    if full:
        return full, preview
    return (preview, None) if preview else None


# #UFB-0057
def _single_image(src: dict) -> list[_Img]:
    previews = ((src.get("preview") or {}).get("images")) or []
    preview = _https(((previews[0] if previews else {}).get("source") or {}).get("url"))
    link = _https(src.get("url_overridden_by_dest") or src.get("url"))
    is_image = src.get("post_hint") == "image" or (
        link and urlparse(link).hostname == "i.redd.it"
    )
    if is_image and link:
        return [_Img("main", link, preview if preview != link else None)]
    if preview and not src.get("is_self"):
        return [_Img("main", preview)]
    return []


# #UFB-0057
def _images(src: dict, inline_ids: list[str]) -> list[_Img]:
    """Gallery items, then inline images, then any other attachment; a post
    with none of those falls back to its single image or link preview."""
    meta = src.get("media_metadata") or {}
    gallery = (src.get("gallery_data") or {}).get("items") or []
    found: list[_Img] = []
    seen: set[str] = set()
    keys = [i.get("media_id") for i in gallery if isinstance(i, dict)]
    for key in [*keys, *inline_ids, *meta]:
        if key in seen or key not in meta:
            continue
        seen.add(key)
        if urls := _meta_urls(meta[key]):
            found.append(_Img(key, *urls))
    return found or _single_image(src)


# #UFB-0057
def _hls_url(src: dict) -> str | None:
    if not src.get("is_video"):
        return None
    video = (src.get("secure_media") or src.get("media") or {}).get("reddit_video")
    return _https((video or {}).get("hls_url"))


# #UFB-0057
def _user_url(name: str) -> str | None:
    if not name or name == "[deleted]":
        return None
    return f"https://www.reddit.com/user/{quote(name)}/"


# #UFB-0057
def _sub_url(name: str) -> str:
    return f"https://www.reddit.com/r/{quote(name)}/"


# #UFB-0057
def _section(
    item: dict, *, title: str | None, heading: str | None = None, album: bool = True
) -> tuple[_Section, str]:
    """A post's or comment's page section, and its plain-text body."""
    src = (item.get("crosspost_parent_list") or [item])[
        0
    ]  # a crosspost shows its source
    body = _s(item.get("body") if "body" in item else item.get("selftext"))
    text, inline_ids = _inline(
        body or _s(src.get("selftext")), src.get("media_metadata") or {}
    )
    images = _images(src, inline_ids)
    for image in images:
        image.album = album
    author = _s(item.get("author"))
    subreddit = _s(item.get("subreddit"))
    return (
        _Section(
            title=title,
            heading=heading,
            author=f"u/{author}" if author else None,
            author_url=_user_url(author),
            subreddit=f"r/{subreddit}" if subreddit else None,
            subreddit_url=_sub_url(subreddit) if subreddit else None,
            body=text,
            images=images,
        ),
        _plain(text),
    )


# #UFB-0057
def _fetch_thread(link: RedditLink, url: str) -> _Fetched:
    params = {"limit": 1, "depth": 1}
    if link.comment_id:
        params.update(comment=link.comment_id, context=0)
    data = _api_get(f"/comments/{link.post_id}", **params)
    try:
        post = data[0]["data"]["children"][0]["data"]
    except (KeyError, IndexError, TypeError) as e:
        raise RedditError("Unexpected Reddit post payload") from e
    title = _s(post.get("title"))
    subreddit = _s(post.get("subreddit"))

    comment = None
    if link.comment_id:
        try:
            children = data[1]["data"]["children"]
        except (KeyError, IndexError, TypeError) as e:
            raise RedditError("Unexpected Reddit comment payload") from e
        comment = next(
            (
                c["data"]
                for c in children
                if isinstance(c, dict) and c.get("kind") == "t1"
            ),
            None,
        )
        if comment is None:
            raise RedditError("Comment not found")

    if comment is None:
        section, plain = _section(post, title=title)
        score = _count(post.get("score"))
        author = _s(post.get("author"))
        subtitle = f"r/{subreddit}" + (f" · ⬆️ {score}" if score else "")
        record = metadata.trim_reddit(
            title=title,
            uploader=f"u/{author}" if author else None,
            uploader_url=_user_url(author),
            description=plain,
            subtitle=subtitle,
            source_url=url,
        )
        hls = _hls_url((post.get("crosspost_parent_list") or [post])[0])
        return _Fetched("post", record, title, [section], hls_url=hls)

    first, plain = _section(comment, title=f"Comment on: {title}", album=True)
    original, _ = _section(post, title=title, heading="Original post", album=False)
    author = _s(comment.get("author"))
    record = metadata.trim_reddit(
        title=f"Re: {title}",
        uploader=f"u/{author}" if author else None,
        uploader_url=_user_url(author),
        description=plain,
        subtitle=f"r/{subreddit}" if subreddit else None,
        source_url=url,
    )
    page_title = (
        f"Comment by u/{author} on: {title}" if author else f"Comment on: {title}"
    )
    return _Fetched("comment", record, page_title, [first, original])


# #UFB-0057
def _fetch_profile(link: RedditLink, url: str) -> _Fetched:
    try:
        data = _api_get(f"/user/{link.name}/about")["data"]
        name = _s(data["name"])
    except (KeyError, TypeError) as e:
        raise RedditError("Unexpected Reddit profile payload") from e
    if data.get("is_suspended"):
        raise RedditError("Suspended Reddit account")
    sub = data.get("subreddit") or {}
    display = _s(sub.get("title")) or name
    bio = _s(sub.get("public_description"))
    karma = _count(data.get("total_karma"))
    cake = _date(data.get("created_utc"))
    stats = " · ".join(
        part
        for part in (f"⭐ {karma} karma" if karma else "", f"🎂 {cake}" if cake else "")
        if part
    )
    avatar_url = _https(data.get("snoovatar_img")) or _https(
        data.get("icon_img") or sub.get("icon_img")
    )
    banner_url = _https(sub.get("banner_img"))
    record = metadata.trim_reddit(
        title=display,
        uploader=f"u/{name}",
        uploader_url=_user_url(name),
        description=bio,
        subtitle=stats,
        source_url=url,
    )
    section = _Section(
        title=display,
        author=f"u/{name}",
        author_url=_user_url(name),
        subtitle=stats,
        body=bio,
        avatar=_Img("avatar", avatar_url) if avatar_url else None,
    )
    banner = _Img("banner", banner_url, album=False) if banner_url else None
    return _Fetched("profile", record, f"u/{name}", [section], banner=banner)


# #UFB-0057
def _fetch_subreddit(link: RedditLink, url: str) -> _Fetched:
    try:
        data = _api_get(f"/r/{link.name}/about")["data"]
        name = _s(data["display_name"])
    except (KeyError, TypeError) as e:
        raise RedditError("Unexpected Reddit subreddit payload") from e
    title = _s(data.get("title")) or name
    short = _s(data.get("public_description"))
    full = _s(data.get("description")) or short
    members = _count(data.get("subscribers"))
    created = _date(data.get("created_utc"))
    stats = " · ".join(
        part
        for part in (
            f"👥 {members} members" if members else "",
            f"🎂 {created}" if created else "",
            "🔞 NSFW" if data.get("over18") else "",
        )
        if part
    )
    icon_url = _https(data.get("community_icon")) or _https(data.get("icon_img"))
    banner_url = _https(data.get("banner_background_image")) or _https(
        data.get("banner_img")
    )
    record = metadata.trim_reddit(
        title=title,
        uploader=f"r/{name}",
        uploader_url=_sub_url(name),
        description=short or full,
        subtitle=stats,
        source_url=url,
    )
    section = _Section(
        title=title,
        author=f"r/{name}",
        author_url=_sub_url(name),
        subtitle=stats,
        body=full,
        avatar=_Img("icon", icon_url) if icon_url else None,
    )
    banner = _Img("banner", banner_url, album=False) if banner_url else None
    return _Fetched("subreddit", record, f"r/{name}", [section], banner=banner)


# #UFB-0057
def _fetch(link: RedditLink, url: str) -> _Fetched:
    fetch = {
        "post": _fetch_thread,
        "comment": _fetch_thread,
        "profile": _fetch_profile,
        "subreddit": _fetch_subreddit,
    }[link.kind]
    fetched = fetch(link, url)
    if not fetched.record:
        raise RedditError("Nothing to show for this Reddit link")
    fetched.record["reddit"] = fetched.kind
    return fetched


# --- storing ---


# #UFB-0057
def _fetch_image(image: _Img) -> tuple[bytes, str] | None:
    """The image's bytes and file extension, trying its fallback when the
    first URL is unusable (too big for Telegram, not a still image, gone)."""
    for url in (image.url, image.fallback):
        if not url:
            continue
        try:
            response = requests.get(url, headers=_headers(), timeout=_TIMEOUT)
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch Reddit image {url}: {e}")
            continue
        content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
        ext = _IMAGE_TYPES.get(content_type)
        if response.status_code != 200 or not ext or not response.content:
            continue
        if len(response.content) > _MAX_IMAGE_BYTES:
            continue
        return response.content, ext
    return None


# #UFB-0057
def _store(fetched: _Fetched, stem: str, url: str) -> RedditDownload:
    """Cache the images, write the Instant View page and the record
    (blocking; run in a thread)."""
    gallery_dir = os.path.join(settings.CACHE_DIR, "gallery", stem)
    everything = [img for sec in fetched.sections for img in sec.images]
    everything += [sec.avatar for sec in fetched.sections if sec.avatar]
    everything += [fetched.banner] if fetched.banner else []
    # Album images first, so they are 01, 02, ... in display order.
    everything.sort(key=lambda img: not img.album)  # stable
    for index, image in enumerate(everything, start=1):
        got = _fetch_image(image)
        if not got:
            logger.warning(f"Skipping Reddit image {image.url} for {url}")
            continue
        content, ext = got
        image.filename = f"{index:02d}{ext}"
        _write_atomic_bytes(os.path.join(gallery_dir, image.filename), content)

    def public(image: _Img | None) -> str | None:
        if image and image.filename:
            return pages.gallery_image_url(stem, image.filename)
        return None

    view_sections = []
    for sec in fetched.sections:
        view_sections.append(
            {
                "heading": sec.heading,
                "title": sec.title,
                "avatar": public(sec.avatar),
                "author": sec.author,
                "author_url": sec.author_url,
                "subreddit": sec.subreddit,
                "subreddit_url": sec.subreddit_url,
                "subtitle": sec.subtitle,
                "body": sec.body,
                "images": {i.key: public(i) for i in sec.images if public(i)},
            }
        )
    pages.write_reddit_page(
        stem,
        {
            "title": fetched.page_title,
            "description": _plain(fetched.sections[0].body),
            "source_url": url,
            "banner": public(fetched.banner),
            "sections": view_sections,
        },
    )

    album = [i for i in everything if i.album and i.filename]
    record = {**fetched.record, "images": [i.filename for i in album]}
    metadata.write(stem, record)
    metrics.record_downloader("reddit-api")
    return RedditDownload(
        record, [os.path.join(gallery_dir, i.filename) for i in album]
    )


# #UFB-0016, #UFB-0057
def _cached(stem: str) -> RedditDownload | None:
    record = metadata.read(stem)
    if not record or not record.get("reddit"):
        return None
    if record.get("hls_url"):
        path = _cached_media_path(stem)
        if not path:
            return None
        _touch_atime(path)
        return RedditDownload(record, [], path)
    names = record.get("images")
    gallery_dir = os.path.join(settings.CACHE_DIR, "gallery", stem)
    paths = [
        os.path.join(gallery_dir, os.path.basename(n))
        for n in (names if isinstance(names, list) else [])
        if isinstance(n, str)
    ]
    page = pages.reddit_page_path(stem)
    if not os.path.exists(page) or not all(os.path.exists(p) for p in paths):
        return None
    for path in [*paths, page]:
        _touch_atime(path)
    return RedditDownload(record, paths)


# #UFB-0015, #UFB-0016, #UFB-0057
async def reddit_download(url: str) -> RedditDownload:
    """Read a Reddit link through the API and cache what the reply needs.
    Raises RedditError (an UnsupportedUrlError) when Reddit gives nothing."""
    link = parse_link(url)
    if link is None:
        raise RedditError(f"Not a Reddit post, comment, profile or subreddit: {url}")
    stem = url_to_filename_stem(url)
    if cached := _cached(stem):
        metrics.record_cache(hit=True)
        return cached

    fetched = await asyncio.to_thread(_fetch, link, url)
    if fetched.hls_url:
        # yt_dlp_download takes the stem lock itself.
        path = await yt_dlp_download(fetched.hls_url, stem=stem)
        if not path:
            raise RedditError(f"Reddit video download produced no file: {url}")
        record = {**fetched.record, "hls_url": fetched.hls_url}
        metadata.write(stem, record)  # over yt-dlp's generic record
        metrics.record_downloader("reddit-api")
        return RedditDownload(record, [], path)

    async with _url_lock(stem):
        if cached := _cached(stem):
            metrics.record_cache(hit=True)
            return cached
        metrics.record_cache(hit=False)
        return await asyncio.to_thread(_store, fetched, stem, url)
