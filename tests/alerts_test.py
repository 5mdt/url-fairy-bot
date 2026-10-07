# alerts_test.py
# #UFB-0054

import asyncio
import collections
from datetime import date, timedelta

import pytest

from app import alerts, bot, cookie_keepalive, metrics
from app.config import settings


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def env(monkeypatch):
    """Two admin chats, every kind on, a fake clock and a recording send."""
    monkeypatch.setattr(settings, "ADMIN_CHAT_ID", "11, 22")
    for name in (
        "ALERT_COOKIES",
        "ALERT_FAILURE_SPIKE",
        "ALERT_BOT_API",
        "ALERT_YTDLP",
        "ALERT_CACHE",
    ):
        monkeypatch.setattr(settings, name, None)
    monkeypatch.setattr(settings, "ALERT_MIN_INTERVAL", 3600)
    monkeypatch.setattr(settings, "ALERT_FAILURE_SPIKE_MIN_ATTEMPTS", 5)
    monkeypatch.setattr(settings, "ALERT_FAILURE_SPIKE_WINDOW_MINUTES", 10)
    monkeypatch.setattr(settings, "ALERT_FAILURE_SPIKE_RATIO", 0.5)
    monkeypatch.setattr(settings, "ALERT_YTDLP_MAX_AGE_DAYS", 60)
    monkeypatch.setattr(settings, "ALERT_CACHE_FULL_PERCENT", 90)
    # Healthy by default.
    monkeypatch.setattr(cookie_keepalive, "cookies_alive", lambda: True)
    monkeypatch.setattr(bot, "is_telegram_api_reachable", lambda: True)
    monkeypatch.setattr(
        alerts, "_ytdlp_version", lambda: date.today().strftime("%Y.%m.%d")
    )
    monkeypatch.setattr(alerts, "_cache_used_percent", lambda: 10.0)
    metrics.reset()
    sent = []

    async def send(chat_id, text):
        sent.append((chat_id, text))

    clock = Clock()
    return alerts.Alerter(send, clock=clock), sent, clock


def run(coro):
    return asyncio.run(coro)


# --- switches ---


# #UFB-0054
def test_kinds_default_to_admin_chat_id_presence(monkeypatch):
    monkeypatch.setattr(settings, "ALERT_COOKIES", None)
    monkeypatch.setattr(settings, "ADMIN_CHAT_ID", "")
    assert alerts.enabled("cookies") is False
    monkeypatch.setattr(settings, "ADMIN_CHAT_ID", "5")
    assert alerts.enabled("cookies") is True


# #UFB-0054
def test_explicit_switch_wins_but_needs_an_admin_chat(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_CHAT_ID", "5")
    monkeypatch.setattr(settings, "ALERT_CACHE", False)
    assert alerts.enabled("cache") is False
    monkeypatch.setattr(settings, "ADMIN_CHAT_ID", "")
    monkeypatch.setattr(settings, "ALERT_CACHE", True)
    assert alerts.enabled("cache") is False


# #UFB-0054
def test_empty_admin_chat_sends_nothing(env, monkeypatch):
    alerter, sent, _ = env
    monkeypatch.setattr(settings, "ADMIN_CHAT_ID", "")
    monkeypatch.setattr(bot, "is_telegram_api_reachable", lambda: False)
    run(alerter.tick())
    assert sent == []


# #UFB-0054
def test_switched_off_kind_sends_nothing(env, monkeypatch):
    alerter, sent, _ = env
    monkeypatch.setattr(settings, "ALERT_BOT_API", False)
    monkeypatch.setattr(bot, "is_telegram_api_reachable", lambda: False)
    run(alerter.tick())
    assert sent == []


# --- de-duplication, recovery, rate limit ---


# #UFB-0054
def test_persistent_fault_sends_once_then_one_recovery(env, monkeypatch):
    alerter, sent, clock = env
    monkeypatch.setattr(bot, "is_telegram_api_reachable", lambda: False)
    for _ in range(4):
        run(alerter.tick())
        clock.t += 60
    assert sorted(c for c, _ in sent) == [11, 22]  # one message per admin chat
    monkeypatch.setattr(bot, "is_telegram_api_reachable", lambda: True)
    run(alerter.tick())
    run(alerter.tick())
    assert len(sent) == 4  # plus one recovery per chat, no repeats
    assert "recovered" in sent[-1][1].lower()


# #UFB-0054
def test_unconfigured_bot_api_is_never_faulty(env, monkeypatch):
    alerter, sent, _ = env
    monkeypatch.setattr(bot, "is_telegram_api_reachable", lambda: None)
    run(alerter.tick())
    assert sent == []


# #UFB-0054
def test_flapping_fault_is_rate_limited(env, monkeypatch):
    alerter, sent, clock = env
    state = {"up": False}
    monkeypatch.setattr(bot, "is_telegram_api_reachable", lambda: state["up"])
    run(alerter.tick())  # alert
    state["up"] = True
    clock.t += 60
    run(alerter.tick())  # recovery
    state["up"] = False
    clock.t += 60
    run(alerter.tick())  # too soon: suppressed
    assert len(sent) == 4
    clock.t += 3600
    run(alerter.tick())  # interval elapsed: alerts again
    assert len(sent) == 6


# #UFB-0054
def test_failed_send_is_retried_next_tick(env, monkeypatch):
    _, _, clock = env
    calls = []

    async def flaky(chat_id, text):
        calls.append(chat_id)
        if len(calls) <= 2:
            raise RuntimeError("telegram down")

    alerter = alerts.Alerter(flaky, clock=clock)
    monkeypatch.setattr(bot, "is_telegram_api_reachable", lambda: False)
    run(alerter.tick())
    run(alerter.tick())
    assert calls == [11, 22, 11, 22]
    run(alerter.tick())
    assert len(calls) == 4  # delivered on the retry: now de-duplicated


# --- individual conditions ---


# #UFB-0054
def test_cookie_alert_and_unknown_state(env, monkeypatch):
    alerter, sent, _ = env
    monkeypatch.setattr(cookie_keepalive, "cookies_alive", lambda: False)
    run(alerter.tick())
    assert len(sent) == 2 and "cookie" in sent[0][1].lower()
    monkeypatch.setattr(cookie_keepalive, "cookies_alive", lambda: None)
    run(alerter.tick())
    assert len(sent) == 2  # unknown changes nothing


# #UFB-0054
def test_failure_spike_is_windowed_per_platform(env):
    alerter, sent, clock = env
    run(alerter.tick())  # baseline
    for _ in range(2):
        metrics.record_download_outcome("tiktok", "success")
    for _ in range(4):
        metrics.record_download_outcome("tiktok", "failure")
    metrics.record_download_outcome("youtube", "failure")
    clock.t += 60
    run(alerter.tick())
    assert len(sent) == 2
    assert "tiktok" in sent[0][1] and "youtube" not in sent[0][1]
    # Later the window slides past the burst: recovery.
    clock.t += 11 * 60
    run(alerter.tick())
    clock.t += 60
    run(alerter.tick())
    assert len(sent) == 4 and "recovered" in sent[-1][1].lower()


# #UFB-0054
def test_failure_spike_needs_min_attempts_and_ratio(env):
    alerter, sent, clock = env
    run(alerter.tick())
    for _ in range(4):  # below the 5-attempt minimum
        metrics.record_download_outcome("reddit", "failure")
    for _ in range(3):
        metrics.record_download_outcome("twitter", "success")
    for _ in range(3):  # exactly 50 percent is not "more than"
        metrics.record_download_outcome("twitter", "failure")
    clock.t += 60
    run(alerter.tick())
    assert sent == []


# #UFB-0054
def test_ytdlp_outdated(env, monkeypatch):
    alerter, sent, _ = env
    old = (date.today() - timedelta(days=61)).strftime("%Y.%m.%d")
    monkeypatch.setattr(alerts, "_ytdlp_version", lambda: old)
    run(alerter.tick())
    assert len(sent) == 2 and "yt-dlp" in sent[0][1]


# #UFB-0054
def test_ytdlp_unparseable_version_is_not_faulty(env, monkeypatch):
    alerter, sent, _ = env
    monkeypatch.setattr(alerts, "_ytdlp_version", lambda: "weird")
    run(alerter.tick())
    assert sent == []


# #UFB-0054
def test_cache_nearly_full(env, monkeypatch):
    alerter, sent, _ = env
    monkeypatch.setattr(alerts, "_cache_used_percent", lambda: 95.0)
    run(alerter.tick())
    assert len(sent) == 2 and "cache" in sent[0][1].lower()


# #UFB-0054
def test_cache_used_percent_reads_the_volume(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    usage = collections.namedtuple("usage", "total used free")
    monkeypatch.setattr(alerts.shutil, "disk_usage", lambda p: usage(200, 150, 50))
    assert alerts._cache_used_percent() == 75.0


# --- lifecycle ---


# #UFB-0054
@pytest.mark.asyncio
async def test_start_is_a_noop_without_admin_chat(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_CHAT_ID", "")
    alerts.start_alerts()
    assert alerts._task is None
    await alerts.stop_alerts()
