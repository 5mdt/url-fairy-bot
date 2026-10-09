# metadata.py
# -*- coding: utf-8 -*-
# #UFB-0041: the shared link-metadata store. One small JSON record per
# downloaded link at CACHE_DIR/meta/<stem>.json, keyed by the URL's cache stem
# (#UFB-0016). #UFB-0048, #UFB-0050, #UFB-0051 and #UFB-0047 build on
# read/write/lookup; unknown keys in a record are kept untouched.

import json
import logging
import os
from datetime import datetime, timezone
from html import escape
from urllib.parse import quote

from app.config import settings

logger = logging.getLogger(__name__)

MAX_DESCRIPTION_CHARS = 100_000
_MAX_TITLE_CHARS = 500

# Caption (title, uploader, excerpt) limits, tried in order until the escaped
# HTML fits the budget: the excerpt shrinks first, then everything else.
_CAPTION_STEPS = (
    (200, 80, 300),
    (200, 80, 200),
    (200, 80, 120),
    (200, 80, 60),
    (200, 80, 0),
    (120, 60, 0),
    (60, 40, 0),
    (30, 20, 0),
    (15, 10, 0),
)

# #UFB-0057: extra, longer excerpt sizes for text-only replies.
_LONG_EXCERPTS = (3500, 3000, 2500, 2000, 1500, 1000, 600)


# #UFB-0041
def _stem(name: str) -> str:
    """The cache stem of a stem, a media file name or a path to one."""
    return os.path.splitext(os.path.basename(name))[0]


# #UFB-0041
def meta_path(name: str) -> str:
    """CACHE_DIR/meta/<stem>.json for a stem or media file name."""
    return os.path.join(settings.CACHE_DIR, "meta", f"{_stem(name)}.json")


# #UFB-0041
def subs_dir(name: str) -> str:
    """CACHE_DIR/subs/<stem>/, where a link's subtitle files live."""
    return os.path.join(settings.CACHE_DIR, "subs", _stem(name))


# #UFB-0041
def subtitle_url(name: str, subtitle_filename: str) -> str:
    return (
        f"https://{settings.BASE_URL}/subs/{quote(_stem(name))}/"
        f"{quote(os.path.basename(subtitle_filename))}"
    )


# #UFB-0041
def _str(value, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value[:limit] if value else None


# #UFB-0041
def _record(
    *,
    title,
    uploader,
    uploader_url=None,
    description=None,
    avatar_url=None,
    subtitles=None,
    source_url=None,
    extractor=None,
    duration=None,
    subtitle=None,
) -> dict | None:
    record = {
        "title": _str(title, _MAX_TITLE_CHARS),
        "uploader": _str(uploader, _MAX_TITLE_CHARS),
        "uploader_url": _str(uploader_url, 2000),
        "description": _str(description, MAX_DESCRIPTION_CHARS),
        "avatar_url": _str(avatar_url, 2000),
        "subtitles": [s for s in (subtitles or []) if isinstance(s, str)],
        "source_url": _str(source_url, 4000),
        "extractor": _str(extractor, 100),
        "duration": duration if isinstance(duration, (int, float)) else None,
        "subtitle": _str(subtitle, 300),
    }
    record = {k: v for k, v in record.items() if v not in (None, [])}
    if not any(k in record for k in ("title", "uploader", "description")):
        return None
    record["saved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return record


# #UFB-0041
def trim_info(
    info, *, source_url: str | None = None, subtitles: list[str] | None = None
) -> dict | None:
    """The trimmed record for a yt-dlp info dict, or None when there is
    nothing worth keeping (not a dict, or no title/uploader/description)."""
    if isinstance(info, dict) and isinstance(info.get("entries"), list):
        info = next((e for e in info["entries"] if isinstance(e, dict)), None)
    if not isinstance(info, dict):
        return None
    return _record(
        title=info.get("title"),
        uploader=info.get("uploader") or info.get("channel"),
        uploader_url=info.get("uploader_url") or info.get("channel_url"),
        description=info.get("description"),
        avatar_url=info.get("uploader_avatar") or info.get("channel_avatar"),
        subtitles=subtitles,
        source_url=source_url or info.get("webpage_url"),
        extractor=info.get("extractor_key") or info.get("extractor"),
        duration=info.get("duration"),
    )


# #UFB-0041, #UFB-0039
def _tiktok_avatar(thumb) -> str | None:
    """TikTok sends `avatarThumb` as a URL string, or as `{"urlList": [...]}`."""
    if isinstance(thumb, dict):
        urls = thumb.get("urlList")
        thumb = urls[0] if isinstance(urls, list) and urls else None
    return thumb if isinstance(thumb, str) else None


# #UFB-0041, #UFB-0039
def trim_tiktok_item(item, *, source_url: str | None = None) -> dict | None:
    """The trimmed record for a TikTok photo post's raw item data."""
    if not isinstance(item, dict):
        return None
    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    avatar = _tiktok_avatar(author.get("avatarThumb"))
    desc = item.get("desc")
    return _record(
        title=desc,
        uploader=author.get("nickname") or author.get("uniqueId"),
        description=desc,
        avatar_url=avatar,
        source_url=source_url,
        extractor="TikTok",
    )


# #UFB-0057
def trim_reddit(
    *,
    title,
    uploader,
    uploader_url=None,
    description=None,
    avatar_url=None,
    subtitle=None,
    source_url: str | None = None,
) -> dict | None:
    """The trimmed record for a Reddit post, comment, profile or subreddit;
    `subtitle` is a short stats line shown under the uploader."""
    return _record(
        title=title,
        uploader=uploader,
        uploader_url=uploader_url,
        description=description,
        avatar_url=avatar_url,
        subtitle=subtitle,
        source_url=source_url,
        extractor="Reddit",
    )


# #UFB-0041
def write(name: str, record: dict | None) -> str | None:
    """Atomically store `record` for a stem or media file name; returns the
    path, or None when there is nothing to store or the write fails."""
    if not record:
        return None
    path = meta_path(name)
    tmp_path = f"{path}.tmp"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False)
        os.replace(tmp_path, path)
    except (OSError, TypeError, ValueError) as e:
        logger.warning(f"Failed to write metadata for {name}: {e}")
        return None
    return path


# #UFB-0041
def read(name: str) -> dict | None:
    """The stored record for a stem or media file name, or None when it is
    missing or unreadable."""
    try:
        with open(meta_path(name), "r", encoding="utf-8") as f:
            record = json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        logger.warning(f"Failed to read metadata for {name}: {e}")
        return None
    return record if isinstance(record, dict) else None


# #UFB-0041
def lookup(url: str) -> dict | None:
    """The stored record for a (resolved) link URL, or None."""
    from app.download import url_to_filename_stem  # download imports this module

    return read(url_to_filename_stem(url))


# #UFB-0041
def delete(name: str) -> bool:
    """Remove the record for a stem or media file name; True if one existed."""
    try:
        os.remove(meta_path(name))
        return True
    except FileNotFoundError:
        return False
    except OSError as e:
        logger.warning(f"Failed to delete metadata for {name}: {e}")
        return False


# #UFB-0041
def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


_MAX_LINKED_URL = 300  # a longer profile URL would eat the caption budget


# #UFB-0041
def _dedupe(title: str, description: str) -> tuple[str, str]:
    """Show the text once (TikTok sends the same text as title and description).
    The shorter one is dropped when the longer contains it, ignoring case and a
    title's trailing `…` or `...`; equal text keeps the title."""
    title, description = " ".join(title.split()), " ".join(description.split())
    stem = title.rstrip(".…").strip().lower()
    if not stem or not description:
        return title, description
    low = description.lower()
    if low == title.lower():
        return title, ""
    if stem in low:
        return "", description
    if low in title.lower():
        return title, ""
    return title, description


# #UFB-0041
def caption(
    record: dict | None,
    budget: int,
    more_url: str | None = None,
    long_excerpt: bool = False,
) -> str:
    """Telegram HTML for the short form: bold title, 👤 uploader (linked to the
    profile when it is a short https URL), description excerpt as a quote. The
    result is at most `budget` characters (markup
    and escapes included), or "" when nothing fits. With `more_url`, a
    `📖 Read more` line follows whenever the description is clipped or left out.
    `long_excerpt` (#UFB-0057, for text-only replies with a large budget) tries
    excerpts longer than 300 characters before the usual steps."""
    if not record or budget <= 0:
        return ""
    title = str(record.get("title") or "")
    uploader = str(record.get("uploader") or "")
    description = str(record.get("description") or "")
    title, description = _dedupe(title, description)
    subtitle = str(record.get("subtitle") or "")
    profile = str(record.get("uploader_url") or "")
    if not (profile.startswith("https://") and len(profile) <= _MAX_LINKED_URL):
        profile = ""
    steps = _CAPTION_STEPS
    if long_excerpt:
        steps = tuple((200, 80, e) for e in _LONG_EXCERPTS) + steps
    for title_max, uploader_max, excerpt_max in steps:
        lines = []
        if clipped := _clip(title, title_max):
            lines.append(f"<b>{escape(clipped)}</b>")
        if clipped := _clip(uploader, uploader_max):
            name = escape(clipped)
            if profile:
                name = f'<a href="{escape(profile)}">{name}</a>'
            lines.append(f"👤 {name}")
        if clipped := _clip(subtitle, uploader_max * 2):
            lines.append(escape(clipped))
        if clipped := _clip(description, excerpt_max):
            lines.append(f"<blockquote>{escape(clipped)}</blockquote>")
        if more_url and description and clipped != description:
            lines.append(f'<a href="{escape(more_url)}">📖 Read more</a>')
        html = "\n".join(lines)
        if len(html) <= budget:
            return html
    return ""
