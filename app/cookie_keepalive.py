# cookie_keepalive.py
# -*- coding: utf-8 -*-
# #UFB-0038

import glob
import logging
import os
import tempfile
import threading
from dataclasses import dataclass
from typing import Callable

import requests
from yt_dlp.cookies import YoutubeDLCookieJar

from app import download
from app.config import settings

logger = logging.getLogger(__name__)

CHECK_TIMEOUT = 5  # seconds per request; the jar lock is held while checking
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"
_REDIRECTS = (301, 302, 303, 307, 308)

_thread: threading.Thread | None = None
_stop = threading.Event()
_last: bool | None = None


# #UFB-0038
def _login_redirect_classifier(
    *markers: str,
) -> Callable[[requests.Response], bool | None]:
    """200 → alive; a redirect to a login page → logged out; else unknown."""

    def classify(resp: requests.Response) -> bool | None:
        if resp.status_code == 200:
            return True
        if resp.status_code in _REDIRECTS:
            location = resp.headers.get("Location", "")
            if any(marker in location for marker in markers):
                return False
        return None

    return classify


# #UFB-0038
def _classify_tiktok(resp: requests.Response) -> bool | None:
    if resp.status_code != 200:
        return None
    try:
        body = resp.json()
    except ValueError:
        return None
    if not isinstance(body, dict) or "message" not in body:
        return None
    data = body.get("data")
    if body["message"] == "success" and isinstance(data, dict) and data.get("username"):
        return True
    return False


# #UFB-0038, #UFB-0057
def _classify_reddit(resp: requests.Response) -> bool | None:
    """`/api/me.json`: an object with `data.name` is a logged-in session,
    an object without `data` (Reddit sends `{}`) a logged-out one."""
    if resp.status_code != 200:
        return None
    try:
        body = resp.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    data = body.get("data")
    return bool(isinstance(data, dict) and data.get("name"))


# #UFB-0038
@dataclass(frozen=True)
class Site:
    name: str
    domain: str  # cookie domain suffix, no leading dot
    url: str  # a page that only a logged-in session can load
    classify: Callable[[requests.Response], bool | None]


SITES = [
    Site(
        "instagram",
        "instagram.com",
        "https://www.instagram.com/accounts/edit/",
        _login_redirect_classifier("/accounts/login"),
    ),
    Site(
        "youtube",
        "youtube.com",
        "https://www.youtube.com/account",
        _login_redirect_classifier("accounts.google.com", "ServiceLogin"),
    ),
    Site(
        "tiktok",
        "tiktok.com",
        "https://www.tiktok.com/passport/web/account/info/",
        _classify_tiktok,
    ),
    Site(
        "reddit",
        "reddit.com",
        "https://www.reddit.com/api/me.json",
        _classify_reddit,
    ),
]


# #UFB-0038
def keepalive_enabled() -> bool:
    return settings.COOKIE_JAR_ENABLED and settings.COOKIE_KEEPALIVE_INTERVAL > 0


# #UFB-0038
def _domain_matches(cookie_domain: str, site: Site) -> bool:
    domain = cookie_domain.lstrip(".")
    return domain == site.domain or domain.endswith("." + site.domain)


# #UFB-0038
def _site_cookies(jar: YoutubeDLCookieJar, site: Site) -> list:
    return [c for c in jar if _domain_matches(c.domain, site)]


# #UFB-0038
def _load_jar(path: str) -> YoutubeDLCookieJar:
    jar = YoutubeDLCookieJar(path)
    jar.load(ignore_discard=True, ignore_expires=True)
    return jar


# #UFB-0038
def _read_recorded_mtime() -> float | None:
    try:
        with open(download.cookie_sources_sidecar_path(), encoding="utf-8") as f:
            return float(f.read().strip())
    except OSError, ValueError:
        pass
    try:  # No sidecar yet (jar predates #UFB-0038): the jar's own age is the baseline.
        return os.path.getmtime(download.COOKIE_JAR_PATH)
    except OSError:
        return None


# #UFB-0038
def _sync_jar(sources: list[str]) -> None:
    """Rebuild the jar when it is missing or a source file is newer than the
    last merge."""
    newest = max(os.path.getmtime(p) for p in sources)
    recorded = _read_recorded_mtime()
    if recorded is None or newest > recorded:
        logger.info("Cookie sources changed; rebuilding the cookie jar")
        download.write_cookie_jar(sources)
    elif not os.path.exists(download.cookie_sources_sidecar_path()):
        _record_sidecar(newest)


# #UFB-0038
def _record_sidecar(newest: float) -> None:
    try:
        with open(download.cookie_sources_sidecar_path(), "w", encoding="utf-8") as f:
            f.write(repr(newest))
    except OSError as e:
        logger.warning(f"Failed to record cookie source mtime: {e}")


# #UFB-0038
def _check_site(jar: YoutubeDLCookieJar, site: Site) -> bool | None:
    session = requests.Session()
    session.cookies = jar
    session.headers["User-Agent"] = USER_AGENT
    try:
        resp = session.get(site.url, allow_redirects=False, timeout=CHECK_TIMEOUT)
    except requests.RequestException as e:
        logger.warning(f"Cookie check for {site.name} failed: {e}")
        return None
    return site.classify(resp)


# #UFB-0038
def _reseed_site(jar: YoutubeDLCookieJar, site: Site, sources: list[str]) -> None:
    """Replace only this site's cookies in the jar with the source files' copy."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".txt", encoding="utf-8"
    )
    tmp.close()
    try:
        download._write_merged_cookies(tmp.name, sources)
        fresh = _load_jar(tmp.name)
    finally:
        os.unlink(tmp.name)
    for cookie in _site_cookies(jar, site):
        jar.clear(cookie.domain, cookie.path, cookie.name)
    for cookie in _site_cookies(fresh, site):
        jar.set_cookie(cookie)


# #UFB-0038
def _overall(results: dict[str, bool | None]) -> bool | None:
    if any(r is False for r in results.values()):
        return False
    if any(r is True for r in results.values()):
        return True
    return None


# #UFB-0038
def check_once() -> bool | None:
    """One keepalive tick. Returns the overall state: False if any site is
    logged out, True if every checked site is alive, None if nothing could
    be determined."""
    global _last
    sources = glob.glob(os.path.join(settings.COOKIES_DIR, "cookies*.txt"))
    if not sources:
        _last = None
        return None

    results: dict[str, bool | None] = {}
    with download.COOKIE_JAR_LOCK:
        _sync_jar(sources)
        jar = _load_jar(download.COOKIE_JAR_PATH)
        for site in SITES:
            if not _site_cookies(jar, site):
                continue
            result = _check_site(jar, site)
            if result is False:
                logger.warning(f"{site.name} cookies are logged out; re-seeding")
                _reseed_site(jar, site, sources)
                result = _check_site(jar, site)
            if result is False:
                logger.warning(f"{site.name} cookies are still logged out")
            else:
                logger.info(f"{site.name} cookies check: {result}")
            results[site.name] = result
        jar.save(ignore_discard=True, ignore_expires=True)

    _last = _overall(results)
    return _last


# #UFB-0038
def cookies_alive() -> bool | None:
    """The last overall result, for /health. None when keepalive is off."""
    if not keepalive_enabled():
        return None
    if not is_keepalive_alive():
        return False
    return _last


# #UFB-0038
def _run() -> None:
    logger.info(
        f"Cookie keepalive thread started "
        f"(COOKIE_KEEPALIVE_INTERVAL={settings.COOKIE_KEEPALIVE_INTERVAL}s)"
    )
    while not _stop.is_set():
        try:
            check_once()
        except Exception as e:
            logger.warning(f"Cookie keepalive tick failed: {e}")
        _stop.wait(settings.COOKIE_KEEPALIVE_INTERVAL)
    logger.info("Cookie keepalive thread stopped")


# #UFB-0038
def start_keepalive() -> None:
    """Start the keepalive thread; a no-op unless enabled."""
    global _thread
    if not keepalive_enabled():
        return
    _stop.clear()
    _thread = threading.Thread(target=_run, name="cookie-keepalive", daemon=True)
    _thread.start()


# #UFB-0038
def stop_keepalive() -> None:
    """Signal the keepalive thread to stop and wait for it to exit."""
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=5)


# #UFB-0038
def is_keepalive_alive() -> bool:
    return _thread is not None and _thread.is_alive()
