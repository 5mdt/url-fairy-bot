# reports.py
# -*- coding: utf-8 -*-
"""Report-broken-link button (#UFB-0051).

Failure replies carry an inline button. The callback data is only a token
(sha256 of the URL), so the URL and reason are kept in a bounded in-memory
table until the button is pressed. A report is a log line plus a capped
`reports` list in the link's metadata record (#UFB-0041); no user ID is
ever logged or stored.
"""

import hashlib
import logging
import re
import time
from collections import OrderedDict, deque
from datetime import datetime, timezone

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app import messages, metadata, metrics
from app.config import settings
from app.download import url_to_filename_stem

logger = logging.getLogger(__name__)

MAX_PENDING = 1000
MAX_RECORD_REPORTS = 20
_MAX_REPORTED = 10000
_PREFIX = "rb:"
_TOKEN_RE = re.compile(r"[0-9a-f]{16}")

_pending: OrderedDict[str, tuple[str, str]] = OrderedDict()
_reported: OrderedDict[tuple[int, str], None] = OrderedDict()
_hits: dict[int, deque[float]] = {}


# #UFB-0051, #UFB-0013
class FailureReply(str):
    """A failure fallback's text that also knows the URL and the reason
    (`failure` or `fallback_mirror`, the #UFB-0045 outcome labels). It is a
    plain `str` to everything else."""

    url: str
    reason: str

    def __new__(cls, text: str, url: str, reason: str):
        obj = super().__new__(cls, text)
        obj.url = url
        obj.reason = reason
        return obj


# #UFB-0051
def reset() -> None:
    """Forget pending reports, duplicates and rate-limit hits (tests)."""
    _pending.clear()
    _reported.clear()
    _hits.clear()


# #UFB-0051
def token_for(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


# #UFB-0051
def callback_data(token: str) -> str:
    return f"{_PREFIX}{token}"


# #UFB-0051
def parse_callback(data: str | None) -> str | None:
    """The token in `rb:<token>` callback data, or None for anything else."""
    if not data or not data.startswith(_PREFIX):
        return None
    token = data[len(_PREFIX) :]
    return token if _TOKEN_RE.fullmatch(token) else None


# #UFB-0051
def keyboard_for(result) -> InlineKeyboardMarkup | None:
    """The report button for a failure reply (and remember what it reports);
    None for every other reply."""
    if not isinstance(result, FailureReply):
        return None
    token = token_for(result.url)
    _pending[token] = (result.url, result.reason)
    _pending.move_to_end(token)
    while len(_pending) > MAX_PENDING:
        _pending.popitem(last=False)
    button = InlineKeyboardButton(
        text=messages.report("button"), callback_data=callback_data(token)
    )
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


# #UFB-0051
def _limited(user_id: int) -> bool:
    limit = settings.REPORT_RATE_LIMIT
    if limit <= 0:
        return False
    now = time.monotonic()
    hits = _hits.setdefault(user_id, deque())
    while hits and now - hits[0] >= settings.REPORT_RATE_WINDOW:
        hits.popleft()
    if len(hits) >= limit:
        return True
    hits.append(now)
    return False


# #UFB-0051, #UFB-0041
def _annotate(url: str, reason: str, platform: str) -> None:
    stem = url_to_filename_stem(url)
    record = metadata.read(stem) or {}
    entries = record.get("reports")
    entries = entries if isinstance(entries, list) else []
    entries.append(
        {
            "reason": reason,
            "platform": platform,
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )
    record["reports"] = entries[-MAX_RECORD_REPORTS:]
    metadata.write(stem, record)


# #UFB-0051
def submit(user_id: int, token: str) -> str:
    """Handle a press: `expired` (unknown token), `duplicate` (this user
    already reported this link), `limited` (over the per-user limit) or
    `thanks` (recorded)."""
    entry = _pending.get(token)
    if entry is None:
        return "expired"
    if (user_id, token) in _reported:
        return "duplicate"
    if _limited(user_id):
        return "limited"
    _reported[(user_id, token)] = None
    while len(_reported) > _MAX_REPORTED:
        _reported.popitem(last=False)
    url, reason = entry
    platform = metrics.platform_for(url)
    logger.warning(f"Broken link report: url={url} reason={reason} platform={platform}")
    _annotate(url, reason, platform)
    return "thanks"
