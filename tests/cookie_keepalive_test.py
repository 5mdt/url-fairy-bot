# cookie_keepalive_test.py
# #UFB-0038

import os
import time

import pytest
import requests

from app import cookie_keepalive as ck
from app.config import settings

INSTAGRAM = ".instagram.com\tTRUE\t/\tTRUE\t2000000000\tsessionid\t{}\n"
YOUTUBE = ".youtube.com\tTRUE\t/\tTRUE\t2000000000\tyt_token\t{}\n"


class FakeResp:
    def __init__(self, status=200, location="", body=None):
        self.status_code = status
        self.headers = {"Location": location} if location else {}
        self._body = body

    def json(self):
        if self._body is None:
            raise ValueError("not json")
        return self._body


def _site(name):
    return next(s for s in ck.SITES if s.name == name)


def _jar_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "COOKIES_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "COOKIE_JAR_ENABLED", True)
    monkeypatch.setattr(settings, "COOKIE_KEEPALIVE_INTERVAL", 3600)
    jar = str(tmp_path / "cookie_jar.txt")
    monkeypatch.setattr("app.download.COOKIE_JAR_PATH", jar)
    monkeypatch.setattr(ck, "_last", None)
    return tmp_path, jar


def _write_source(tmp_path, *lines, name="cookies.txt"):
    path = tmp_path / name
    path.write_text("# Netscape HTTP Cookie File\n" + "".join(lines), encoding="utf-8")
    return path


def _patch_get(monkeypatch, handler):
    monkeypatch.setattr(requests.Session, "get", handler)


def _alive_get(self, url, **kwargs):
    return FakeResp(200, body={"message": "success", "data": {"username": "u"}})


# --- per-site classifiers ---


@pytest.mark.parametrize("name", ["instagram", "youtube"])
def test_redirect_sites_classify_alive_logged_out_and_unknown(name):
    site = _site(name)
    assert site.classify(FakeResp(200)) is True
    login = "https://www.instagram.com/accounts/login/?next=/accounts/edit/"
    if name == "youtube":
        login = "https://accounts.google.com/ServiceLogin?service=youtube"
    assert site.classify(FakeResp(302, location=login)) is False
    assert site.classify(FakeResp(302, location="https://example.com/x")) is None
    assert site.classify(FakeResp(500)) is None


def test_tiktok_classifies_alive_logged_out_and_unknown():
    site = _site("tiktok")
    ok = {"message": "success", "data": {"username": "someone"}}
    assert site.classify(FakeResp(200, body=ok)) is True
    assert site.classify(FakeResp(200, body={"message": "error"})) is False
    assert site.classify(FakeResp(200)) is None  # not JSON
    assert site.classify(FakeResp(503, body=ok)) is None


# --- check_once ---


def test_check_once_builds_jar_and_reports_alive(env, monkeypatch):
    tmp_path, jar = env
    _write_source(tmp_path, INSTAGRAM.format("abc"))
    _patch_get(monkeypatch, _alive_get)

    assert ck.check_once() is True
    assert "sessionid\tabc" in _jar_text(jar)


def test_check_once_without_sources_returns_none(env, monkeypatch):
    _patch_get(monkeypatch, _alive_get)
    assert ck.check_once() is None


def test_check_once_without_known_site_cookies_returns_none(env, monkeypatch):
    tmp_path, _ = env
    _write_source(tmp_path, ".other.example\tTRUE\t/\tTRUE\t2000000000\tx\ty\n")
    _patch_get(monkeypatch, _alive_get)
    assert ck.check_once() is None


def test_network_error_is_unknown_not_dead(env, monkeypatch):
    tmp_path, jar = env
    _write_source(tmp_path, INSTAGRAM.format("abc"))

    def boom(self, url, **kwargs):
        raise requests.ConnectionError("down")

    _patch_get(monkeypatch, boom)
    assert ck.check_once() is None
    assert "sessionid\tabc" in _jar_text(jar)  # not re-seeded or dropped


def test_unchanged_sources_leave_jar_alone(env, monkeypatch):
    tmp_path, jar = env
    _write_source(tmp_path, INSTAGRAM.format("abc"))
    _patch_get(monkeypatch, _alive_get)
    ck.check_once()

    with open(jar, "a", encoding="utf-8") as f:
        f.write(YOUTUBE.format("only_in_jar"))
    ck.check_once()

    assert "only_in_jar" in _jar_text(jar)


def test_newer_sources_rebuild_jar(env, monkeypatch):
    tmp_path, jar = env
    src = _write_source(tmp_path, INSTAGRAM.format("old"))
    _patch_get(monkeypatch, _alive_get)
    ck.check_once()

    src.write_text(
        "# Netscape HTTP Cookie File\n" + INSTAGRAM.format("rotated"), encoding="utf-8"
    )
    future = time.time() + 100
    os.utime(src, (future, future))
    ck.check_once()

    text = _jar_text(jar)
    assert "sessionid\trotated" in text
    assert "sessionid\told" not in text


def test_logged_out_site_is_reseeded_alone_and_rechecked(env, monkeypatch):
    tmp_path, jar = env
    _write_source(tmp_path, INSTAGRAM.format("old"), YOUTUBE.format("yt_old"))
    _patch_get(monkeypatch, _alive_get)
    ck.check_once()

    # Jar now holds a refreshed YouTube token; the operator drops in a new
    # Instagram session. The jar's own state is what the keepalive checks.
    text = _jar_text(jar).replace("yt_old", "yt_refreshed")
    with open(jar, "w", encoding="utf-8") as f:
        f.write(text)
    _write_source(tmp_path, INSTAGRAM.format("new"), YOUTUBE.format("yt_old"))
    # Make the "new" source NOT trigger a full rebuild: it is older than the
    # recorded sidecar baseline.
    past = time.time() - 1000
    os.utime(tmp_path / "cookies.txt", (past, past))

    calls = []

    def get(self, url, **kwargs):
        cookies = {c.name: c.value for c in self.cookies}
        calls.append(url)
        if "instagram" in url and cookies.get("sessionid") == "old":
            return FakeResp(302, location="https://www.instagram.com/accounts/login/")
        return FakeResp(200)

    _patch_get(monkeypatch, get)

    assert ck.check_once() is True
    text = _jar_text(jar)
    assert "sessionid\tnew" in text
    assert "yt_refreshed" in text  # other site's refreshed token kept
    assert sum("instagram" in u for u in calls) == 2  # check + one re-check


def test_still_logged_out_after_reseed_reports_false(env, monkeypatch):
    tmp_path, _ = env
    _write_source(tmp_path, INSTAGRAM.format("abc"))

    def get(self, url, **kwargs):
        return FakeResp(302, location="https://www.instagram.com/accounts/login/")

    _patch_get(monkeypatch, get)
    assert ck.check_once() is False


def test_set_cookie_refresh_is_persisted(env, monkeypatch):
    tmp_path, jar = env
    _write_source(tmp_path, INSTAGRAM.format("abc"))

    def get(self, url, **kwargs):
        for c in self.cookies:
            c.value = "refreshed"
        return FakeResp(200)

    _patch_get(monkeypatch, get)
    ck.check_once()
    assert "sessionid\trefreshed" in _jar_text(jar)


# --- lifecycle / cookies_alive ---


def test_disabled_without_jar(env, monkeypatch):
    monkeypatch.setattr(settings, "COOKIE_JAR_ENABLED", False)
    ck.start_keepalive()
    assert ck.is_keepalive_alive() is False
    assert ck.cookies_alive() is None


def test_disabled_with_zero_interval(env, monkeypatch):
    monkeypatch.setattr(settings, "COOKIE_KEEPALIVE_INTERVAL", 0)
    ck.start_keepalive()
    assert ck.is_keepalive_alive() is False
    assert ck.cookies_alive() is None


def test_enabled_but_thread_dead_reports_false(env, monkeypatch):
    monkeypatch.setattr(ck, "_thread", None)
    assert ck.cookies_alive() is False


def test_thread_runs_first_tick_then_stops(env, monkeypatch):
    tmp_path, _ = env
    _write_source(tmp_path, INSTAGRAM.format("abc"))
    _patch_get(monkeypatch, _alive_get)

    ck.start_keepalive()
    try:
        deadline = time.time() + 5
        while ck.cookies_alive() is not True and time.time() < deadline:
            time.sleep(0.05)
        assert ck.is_keepalive_alive() is True
        assert ck.cookies_alive() is True
    finally:
        ck.stop_keepalive()
    assert ck.is_keepalive_alive() is False
