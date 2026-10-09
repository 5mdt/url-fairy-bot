# metrics.py
# -*- coding: utf-8 -*-
"""Usage metrics (#UFB-0045): in-memory Prometheus counters and histograms.

Every label value comes from a fixed set (platform names plus `other`, a
few outcomes, downloaders and reply kinds), never from a URL or chat ID.
Counters reset on restart. `/stats` (#UFB-0049) and the alerts (#UFB-0054)
read the same numbers through `requests_total`, `download_outcomes`,
`downloader_successes`, `reply_kinds`, `cache_hit_rate` and `snapshot`.
"""

import os
import time
from contextlib import contextmanager
from urllib.parse import urlparse

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from app.config import settings

# Domain suffix -> platform name; anything else is "other".
_DOMAIN_PLATFORMS = {
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "tiktok.com": "tiktok",
    "instagram.com": "instagram",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "reddit.com": "reddit",
    "redd.it": "reddit",
    "threads.com": "threads",
    "threads.net": "threads",
    "spotify.com": "spotify",
}
CONTENT_TYPE = CONTENT_TYPE_LATEST
OTHER = "other"
PLATFORMS = tuple(sorted(set(_DOMAIN_PLATFORMS.values()))) + (OTHER,)
OUTCOMES = ("success", "failure", "fallback_mirror")
# "cobalt" is reserved for #UFB-0052.
DOWNLOADERS = ("yt-dlp", "cobalt", "reddit-api")  # #UFB-0057
REPLY_KINDS = ("native_video", "text_link", "gallery")

_BUCKETS = (0.1, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300)


# #UFB-0045
def platform_for(url: str) -> str:
    """The fixed platform label for `url` (`other` when unknown); only the
    name is returned, never any part of the URL."""
    try:
        host = (urlparse(str(url)).hostname or "").lower()
    except ValueError:
        return OTHER
    for domain, name in _DOMAIN_PLATFORMS.items():
        if host == domain or host.endswith("." + domain):
            return name
    return OTHER


# #UFB-0045
def cache_size_bytes() -> int:
    """Total size of the files under CACHE_DIR (0 when it is unreadable)."""
    total = 0
    for root, _dirs, files in os.walk(settings.CACHE_DIR):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


_registry: CollectorRegistry
_requests: Counter
_downloads: Counter
_downloaders: Counter
_download_seconds: Histogram
_reply_seconds: Histogram
_replies: Counter
_cache_lookups: Counter
_cache_size: Gauge


# #UFB-0045
def reset() -> None:
    """Drop every recorded value and start from zero (used by tests)."""
    global _registry, _requests, _downloads, _downloaders, _download_seconds
    global _reply_seconds, _replies, _cache_lookups, _cache_size
    _registry = CollectorRegistry()
    _requests = Counter(
        "ufb_requests", "Links handled, per platform.", ["platform"], registry=_registry
    )
    _downloads = Counter(
        "ufb_downloads",
        "Download outcomes, per platform.",
        ["platform", "outcome"],
        registry=_registry,
    )
    _downloaders = Counter(
        "ufb_downloader_successes",
        "Successful downloads, per downloader.",
        ["downloader"],
        registry=_registry,
    )
    _download_seconds = Histogram(
        "ufb_download_seconds",
        "Download latency, per platform.",
        ["platform"],
        buckets=_BUCKETS,
        registry=_registry,
    )
    _reply_seconds = Histogram(
        "ufb_reply_seconds",
        "Reply delivery latency, per reply kind.",
        ["kind"],
        buckets=_BUCKETS,
        registry=_registry,
    )
    _replies = Counter(
        "ufb_replies", "Replies sent, per kind.", ["kind"], registry=_registry
    )
    _cache_lookups = Counter(
        "ufb_cache_lookups",
        "Media cache lookups, hit or miss.",
        ["result"],
        registry=_registry,
    )
    _cache_size = Gauge(
        "ufb_cache_size_bytes", "Bytes held in the media cache.", registry=_registry
    )
    _cache_size.set_function(cache_size_bytes)


# #UFB-0045
def _label(value: str, allowed: tuple[str, ...], default: str = OTHER) -> str:
    return value if value in allowed else default


# #UFB-0045
def record_request(platform: str) -> None:
    _requests.labels(_label(platform, PLATFORMS)).inc()


# #UFB-0045
def record_download_outcome(platform: str, outcome: str) -> None:
    """`outcome` is one of OUTCOMES: success, failure, fallback_mirror."""
    if outcome not in OUTCOMES:
        raise ValueError(f"unknown download outcome: {outcome}")
    _downloads.labels(_label(platform, PLATFORMS), outcome).inc()


# #UFB-0045, #UFB-0052
def record_downloader(downloader: str) -> None:
    """Count a download that `downloader` (one of DOWNLOADERS) completed."""
    if downloader not in DOWNLOADERS:
        raise ValueError(f"unknown downloader: {downloader}")
    _downloaders.labels(downloader).inc()


# #UFB-0045
def record_cache(hit: bool) -> None:
    _cache_lookups.labels("hit" if hit else "miss").inc()


# #UFB-0045
def record_reply_kind(kind: str) -> None:
    if kind not in REPLY_KINDS:
        raise ValueError(f"unknown reply kind: {kind}")
    _replies.labels(kind).inc()


# #UFB-0045
def observe_download(platform: str, seconds: float) -> None:
    _download_seconds.labels(_label(platform, PLATFORMS)).observe(seconds)


# #UFB-0045
def observe_reply(kind: str, seconds: float) -> None:
    _reply_seconds.labels(_label(kind, REPLY_KINDS, "text_link")).observe(seconds)


# #UFB-0045
@contextmanager
def timed(observe, label: str):
    """Time the block and pass the seconds to `observe(label, seconds)`,
    also when it raises."""
    start = time.perf_counter()
    try:
        yield
    finally:
        observe(label, time.perf_counter() - start)


# #UFB-0045
def _samples(metric, name: str):
    for family in metric.collect():
        for sample in family.samples:
            if sample.name == name:
                yield sample


# #UFB-0045, #UFB-0049, #UFB-0054
def requests_total() -> dict[str, int]:
    """Requests handled per platform (only platforms seen so far)."""
    return {
        s.labels["platform"]: int(s.value)
        for s in _samples(_requests, "ufb_requests_total")
    }


# #UFB-0045, #UFB-0049, #UFB-0054
def download_outcomes() -> dict[str, dict[str, int]]:
    """{platform: {outcome: count}} for every platform seen so far."""
    out: dict[str, dict[str, int]] = {}
    for s in _samples(_downloads, "ufb_downloads_total"):
        out.setdefault(s.labels["platform"], {})[s.labels["outcome"]] = int(s.value)
    return out


# #UFB-0045, #UFB-0049
def downloader_successes() -> dict[str, int]:
    return {
        s.labels["downloader"]: int(s.value)
        for s in _samples(_downloaders, "ufb_downloader_successes_total")
    }


# #UFB-0045, #UFB-0049
def reply_kinds() -> dict[str, int]:
    return {
        s.labels["kind"]: int(s.value) for s in _samples(_replies, "ufb_replies_total")
    }


# #UFB-0045, #UFB-0049
def cache_hit_rate() -> float | None:
    """Hits / lookups since start, or None before the first lookup."""
    counts = {
        s.labels["result"]: s.value
        for s in _samples(_cache_lookups, "ufb_cache_lookups_total")
    }
    hits, misses = counts.get("hit", 0.0), counts.get("miss", 0.0)
    return hits / (hits + misses) if hits + misses else None


# #UFB-0045, #UFB-0049, #UFB-0054
def snapshot() -> dict:
    """All headline numbers in one plain dict."""
    return {
        "requests": requests_total(),
        "downloads": download_outcomes(),
        "downloaders": downloader_successes(),
        "replies": reply_kinds(),
        "cache_hit_rate": cache_hit_rate(),
        "cache_size_bytes": cache_size_bytes(),
    }


# #UFB-0045
def render() -> bytes:
    """The Prometheus text exposition served at /metrics."""
    return generate_latest(_registry)


reset()
