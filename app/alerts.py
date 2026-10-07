# alerts.py
# -*- coding: utf-8 -*-
# #UFB-0054

import asyncio
import logging
import shutil
import time
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime
from importlib import metadata
from typing import Awaitable, Callable

from app import bot, cookie_keepalive, metrics
from app.config import settings

logger = logging.getLogger(__name__)

SendFn = Callable[[int, str], Awaitable[None]]

KINDS = ("cookies", "failure_spike", "bot_api", "ytdlp", "cache")

_task: asyncio.Task | None = None


# #UFB-0054
def enabled(kind: str) -> bool:
    """Whether alerts of `kind` are on: its ALERT_* switch, or on when unset
    and ADMIN_CHAT_ID is set. Never on without an admin chat."""
    if not settings.admin_chat_ids:
        return False
    switch = getattr(settings, f"ALERT_{kind.upper()}")
    return True if switch is None else bool(switch)


# #UFB-0054
@dataclass
class Condition:
    """One checked fault. `faulty` None means unknown: state is unchanged."""

    key: str  # de-duplication key, e.g. "failure_spike:tiktok"
    kind: str
    faulty: bool | None
    alert: str
    recovery: str


# #UFB-0054
@dataclass
class _State:
    alerted: bool = False
    last_alert: float | None = None


# #UFB-0054
def _ytdlp_version() -> str:
    return metadata.version("yt-dlp")


# #UFB-0054
def _cache_used_percent() -> float | None:
    """Percent used of the volume holding CACHE_DIR (None if unreadable)."""
    try:
        usage = shutil.disk_usage(settings.CACHE_DIR)
    except OSError:
        return None
    return usage.used / usage.total * 100 if usage.total else None


# #UFB-0054
def _cookie_condition() -> Condition:
    alive = cookie_keepalive.cookies_alive()
    return Condition(
        "cookies",
        "cookies",
        None if alive is None else not alive,
        "A cookie jar expired or logged out (or the cookie keepalive stopped). "
        "Re-export the cookie files.",
        "Recovered: the cookie jar is alive again.",
    )


# #UFB-0054
def _bot_api_condition() -> Condition:
    reachable = bot.is_telegram_api_reachable()
    return Condition(
        "bot_api",
        "bot_api",
        None if reachable is None else not reachable,
        "The local Bot API server is unreachable.",
        "Recovered: the local Bot API server is reachable again.",
    )


# #UFB-0054
def _ytdlp_condition() -> Condition:
    version = _ytdlp_version()
    try:
        released = datetime.strptime(version, "%Y.%m.%d").date()
        age = (date.today() - released).days
    except ValueError:
        return Condition("ytdlp", "ytdlp", None, "", "")
    return Condition(
        "ytdlp",
        "ytdlp",
        age > settings.ALERT_YTDLP_MAX_AGE_DAYS,
        f"yt-dlp {version} is {age} days old (limit "
        f"{settings.ALERT_YTDLP_MAX_AGE_DAYS}). Update it.",
        "Recovered: yt-dlp is up to date.",
    )


# #UFB-0054
def _cache_condition() -> Condition:
    percent = _cache_used_percent()
    limit = settings.ALERT_CACHE_FULL_PERCENT
    return Condition(
        "cache",
        "cache",
        None if percent is None else percent >= limit,
        f"The cache volume is {percent or 0:.0f}% full (limit {limit}%).",
        "Recovered: the cache volume has free space again.",
    )


# #UFB-0054
class Alerter:
    """De-duplicating, rate-limited alert sender. `send(chat_id, text)` and
    `clock` are injectable for tests."""

    def __init__(self, send: SendFn, clock: Callable[[], float] = time.monotonic):
        self._send = send
        self._clock = clock
        self._states: dict[str, _State] = {}
        # (time, {platform: (attempts, failures)}); counters start at zero.
        self._history: deque[tuple[float, dict[str, tuple[int, int]]]] = deque(
            [(clock(), {})]
        )

    # #UFB-0054
    def _spike_conditions(self) -> list[Condition]:
        now = self._clock()
        current = {
            p: (o.get("success", 0) + o.get("failure", 0), o.get("failure", 0))
            for p, o in metrics.download_outcomes().items()
        }
        self._history.append((now, current))
        window = settings.ALERT_FAILURE_SPIKE_WINDOW_MINUTES * 60
        while len(self._history) > 2 and self._history[1][0] <= now - window:
            self._history.popleft()
        baseline = self._history[0][1]
        out = []
        for platform in sorted(set(current) | set(self._states_platforms())):
            attempts = (
                current.get(platform, (0, 0))[0] - baseline.get(platform, (0, 0))[0]
            )
            failures = (
                current.get(platform, (0, 0))[1] - baseline.get(platform, (0, 0))[1]
            )
            spike = (
                attempts >= settings.ALERT_FAILURE_SPIKE_MIN_ATTEMPTS
                and failures / attempts > settings.ALERT_FAILURE_SPIKE_RATIO
            )
            out.append(
                Condition(
                    f"failure_spike:{platform}",
                    "failure_spike",
                    spike,
                    f"Download failures on {platform}: {failures} of the last "
                    f"{attempts} attempts failed (within "
                    f"{settings.ALERT_FAILURE_SPIKE_WINDOW_MINUTES} min).",
                    f"Recovered: {platform} downloads are no longer failing.",
                )
            )
        return out

    # #UFB-0054
    def _states_platforms(self) -> list[str]:
        prefix = "failure_spike:"
        return [k[len(prefix) :] for k in self._states if k.startswith(prefix)]

    # #UFB-0054
    def _conditions(self) -> list[Condition]:
        out: list[Condition] = []
        checks = (
            ("cookies", _cookie_condition),
            ("bot_api", _bot_api_condition),
            ("ytdlp", _ytdlp_condition),
            ("cache", _cache_condition),
        )
        for kind, check in checks:
            if enabled(kind):
                try:
                    out.append(check())
                except Exception as e:
                    logger.warning(f"Alert check {kind} failed: {e}")
        if enabled("failure_spike"):
            try:
                out.extend(self._spike_conditions())
            except Exception as e:
                logger.warning(f"Alert check failure_spike failed: {e}")
        return out

    # #UFB-0054
    async def _broadcast(self, text: str) -> bool:
        """Send to every admin chat; True if at least one delivery worked."""
        delivered = False
        for chat_id in settings.admin_chat_ids:
            try:
                await self._send(chat_id, text)
                delivered = True
            except Exception as e:
                logger.warning(f"Failed to send alert to {chat_id}: {e}")
        return delivered

    # #UFB-0054
    async def report(self, cond: Condition) -> None:
        """Apply one check result: alert once, then one recovery notice."""
        if cond.faulty is None:
            return
        state = self._states.setdefault(cond.key, _State())
        now = self._clock()
        if cond.faulty and not state.alerted:
            if (
                state.last_alert is not None
                and now - state.last_alert < settings.ALERT_MIN_INTERVAL
            ):
                return
            if await self._broadcast(f"⚠️ {cond.alert}"):
                state.alerted = True
                state.last_alert = now
        elif not cond.faulty and state.alerted:
            if await self._broadcast(f"✅ {cond.recovery}"):
                state.alerted = False

    # #UFB-0054
    async def tick(self) -> None:
        """Run every enabled check once (blocking checks off the event loop)."""
        conditions = await asyncio.to_thread(self._conditions)
        for cond in conditions:
            await self.report(cond)


# #UFB-0054
async def _send_via_bot(chat_id: int, text: str) -> None:
    await bot.bot.send_message(chat_id, text)


# #UFB-0054
async def _run() -> None:
    alerter = Alerter(_send_via_bot)
    logger.info(
        f"Alerts started (ALERT_CHECK_INTERVAL={settings.ALERT_CHECK_INTERVAL}s)"
    )
    while True:
        try:
            await alerter.tick()
        except Exception as e:
            logger.warning(f"Alert tick failed: {e}")
        await asyncio.sleep(settings.ALERT_CHECK_INTERVAL)


# #UFB-0054
def start_alerts() -> None:
    """Start the periodic checker; a no-op without ADMIN_CHAT_ID."""
    global _task
    if not settings.admin_chat_ids or settings.ALERT_CHECK_INTERVAL <= 0:
        return
    _task = asyncio.get_running_loop().create_task(_run(), name="alerts")


# #UFB-0054
async def stop_alerts() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
