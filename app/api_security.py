# api_security.py
"""#UFB-0056: API key check and per-client rate limit for POST /process_url/."""

import hmac
import ipaddress
import logging
import time
from collections import deque

from fastapi import HTTPException, Request

from .config import settings

logger = logging.getLogger(__name__)


# #UFB-0056
def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


# #UFB-0056
def warn_if_open() -> None:
    """Log a startup warning when API_KEY is unset (endpoint is open)."""
    if not _csv(settings.API_KEY):
        logger.warning(
            "API_KEY is not set: POST /process_url/ accepts unauthenticated requests"
        )


# #UFB-0056
def _is_trusted(address: str, trusted_csv: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    for entry in _csv(trusted_csv):
        try:
            if ip in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            logger.warning(f"Ignoring invalid TRUSTED_PROXIES entry: {entry!r}")
    return False


# #UFB-0056
def client_address(peer: str, forwarded_for: str | None, trusted_csv: str) -> str:
    """The peer address, unless the peer is a trusted proxy: then the rightmost
    X-Forwarded-For entry that is not itself a trusted proxy."""
    if not forwarded_for or not _is_trusted(peer, trusted_csv):
        return peer
    for entry in reversed([e.strip() for e in forwarded_for.split(",")]):
        try:
            ipaddress.ip_address(entry)
        except ValueError:
            return peer
        if not _is_trusted(entry, trusted_csv):
            return entry
    return peer


# #UFB-0056
class RateLimiter:
    """In-memory sliding window; per process, resets on restart."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}

    def check(self, client: str, limit: int, window: int) -> int | None:
        """Count a request. None if allowed, else whole seconds until retry."""
        now = time.monotonic()
        if len(self._hits) > 10_000:
            self._prune(now, window)
        hits = self._hits.setdefault(client, deque())
        while hits and now - hits[0] >= window:
            hits.popleft()
        if len(hits) >= limit:
            return max(1, int(hits[0] + window - now + 0.999))
        hits.append(now)
        return None

    def _prune(self, now: float, window: int) -> None:
        stale = [k for k, h in self._hits.items() if not h or now - h[-1] >= window]
        for key in stale:
            del self._hits[key]

    def clear(self) -> None:
        self._hits.clear()


_limiter = RateLimiter()


# #UFB-0056
def reset_rate_limiter() -> None:
    _limiter.clear()


# #UFB-0056
async def require_api_access(request: Request) -> None:
    """FastAPI dependency: rate limit first (so bad keys count), then API key."""
    if settings.API_RATE_LIMIT > 0:
        peer = request.client.host if request.client else "unknown"
        client = client_address(
            peer, request.headers.get("x-forwarded-for"), settings.TRUSTED_PROXIES
        )
        retry_after = _limiter.check(
            client, settings.API_RATE_LIMIT, settings.API_RATE_WINDOW
        )
        if retry_after is not None:
            raise HTTPException(
                status_code=429,
                detail="Too many requests",
                headers={"Retry-After": str(retry_after)},
            )

    keys = _csv(settings.API_KEY)
    if not keys:
        return
    provided = request.headers.get("x-api-key", "").encode()
    # Compare against every key (no early exit) to keep timing uniform.
    matched = False
    for key in keys:
        if hmac.compare_digest(provided, key.encode()):
            matched = True
    if not matched:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
