# duplicates.py
# -*- coding: utf-8 -*-
# #UFB-0050: remembers, per chat, which bot reply answered which link and for
# how long, so a repeat of the same link points at the earlier reply. One small
# JSON file per normalized URL at CACHE_DIR/replies/<stem>.json, holding
# {"chats": {"<chat_id>": {"message_id": int, "at": epoch_seconds}}}. It uses
# the cache stem and atomic write of the #UFB-0041 metadata store, but a
# separate directory: the key is the URL as posted, which has no media file,
# and the metadata sidecar sweep would delete such a record.

import json
import logging
import os
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.config import settings

logger = logging.getLogger(__name__)

_TRACKING_PARAMS = {"fbclid", "gclid", "igshid", "si", "feature"}


# #UFB-0050
def normalize_url(url: str) -> str:
    """A key for "the same link": lowercase scheme and host, no fragment, no
    trailing slash, tracking parameters (utm_*, fbclid, ...) dropped."""
    parts = urlsplit(url.strip())
    query = urlencode(
        [
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS
        ]
    )
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, "")
    )


# #UFB-0050
def replies_dir() -> str:
    return os.path.join(settings.CACHE_DIR, "replies")


# #UFB-0050
def _path(url: str) -> str:
    from app.download import url_to_filename_stem  # download imports metadata

    return os.path.join(
        replies_dir(), f"{url_to_filename_stem(normalize_url(url))}.json"
    )


# #UFB-0050
def _load(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        logger.warning(f"Failed to read reply record {path}: {e}")
        return {}
    chats = data.get("chats") if isinstance(data, dict) else None
    return chats if isinstance(chats, dict) else {}


# #UFB-0050
def _live(chats: dict, now: float) -> dict:
    return {
        k: v
        for k, v in chats.items()
        if isinstance(v, dict)
        and isinstance(v.get("message_id"), int)
        and isinstance(v.get("at"), (int, float))
        and now - v["at"] < settings.DUPLICATE_WINDOW
    }


# #UFB-0050
def _save(path: str, chats: dict) -> bool:
    tmp_path = f"{path}.tmp"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump({"chats": chats}, f)
        os.replace(tmp_path, path)
        return True
    except (OSError, TypeError, ValueError) as e:
        logger.warning(f"Failed to write reply record {path}: {e}")
        return False


# #UFB-0050
def lookup(chat_id: int, url: str, now: float | None = None) -> int | None:
    """The message ID of this chat's earlier reply for `url`, if one was sent
    within DUPLICATE_WINDOW seconds; None when disabled, unseen or expired."""
    if settings.DUPLICATE_WINDOW <= 0:
        return None
    now = time.time() if now is None else now
    entry = _live(_load(_path(url)), now).get(str(chat_id))
    return entry["message_id"] if entry else None


# #UFB-0050
def record(chat_id: int, url: str, message_id: int, now: float | None = None) -> None:
    """Remember `message_id` as this chat's reply for `url`; failures are
    logged and never propagate."""
    if settings.DUPLICATE_WINDOW <= 0:
        return
    now = time.time() if now is None else now
    path = _path(url)
    chats = _live(_load(path), now)
    chats[str(chat_id)] = {"message_id": message_id, "at": now}
    _save(path, chats)


# #UFB-0050
def forget(chat_id: int, url: str) -> None:
    """Drop this chat's entry for `url` (its earlier reply is gone)."""
    path = _path(url)
    chats = _load(path)
    if chats.pop(str(chat_id), None) is None:
        return
    if chats:
        _save(path, chats)
        return
    try:
        os.remove(path)
    except OSError as e:
        logger.warning(f"Failed to delete reply record {path}: {e}")


# #UFB-0050
def sweep_file(path: str, now: float | None = None) -> bool:
    """Cleanup hook: delete a reply record whose entries have all expired
    (or are unreadable). True if the file was removed."""
    now = time.time() if now is None else now
    if _live(_load(path), now):
        return False
    try:
        os.remove(path)
        return True
    except OSError:
        return False


# #UFB-0050
class ReplyRecorder:
    """Wraps an incoming aiogram message and remembers the ID of the first
    bot reply that goes out through it (reply, reply_video, reply_photo,
    reply_media_group, ...); everything else is delegated untouched."""

    def __init__(self, message):
        self._message = message
        self.first_id: int | None = None

    def __getattr__(self, name):
        attr = getattr(self._message, name)
        if not name.startswith("reply") or not callable(attr):
            return attr

        async def wrapper(*args, **kwargs):
            sent = await attr(*args, **kwargs)
            if self.first_id is None:
                first = sent[0] if isinstance(sent, list) and sent else sent
                message_id = getattr(first, "message_id", None)
                if isinstance(message_id, int):
                    self.first_id = message_id
            return sent

        return wrapper
