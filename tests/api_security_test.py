# api_security_test.py

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app import api_security
from app.config import settings
from app.main import app

URL = "https://tiktok.com/@user/video/1"


async def _post(headers=None, client=("203.0.113.9", 5000)):
    transport = ASGITransport(app=app, client=client)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        return await ac.post("/process_url/", json={"url": URL}, headers=headers)


@pytest.fixture
def ok_processing():
    with patch("app.api.process_url_request", new=AsyncMock(return_value="ok")) as m:
        yield m


# --- API key ---


# #UFB-0056
@pytest.mark.asyncio
async def test_unset_key_leaves_endpoint_open(ok_processing):
    assert (await _post()).status_code == 200


# #UFB-0056
@pytest.mark.asyncio
async def test_missing_key_is_401_and_does_no_work(monkeypatch, ok_processing):
    monkeypatch.setattr(settings, "API_KEY", "secret")
    response = await _post()
    assert response.status_code == 401
    ok_processing.assert_not_awaited()


# #UFB-0056
@pytest.mark.asyncio
async def test_wrong_key_is_401(monkeypatch, ok_processing):
    monkeypatch.setattr(settings, "API_KEY", "secret")
    assert (await _post({"X-API-Key": "nope"})).status_code == 401


# #UFB-0056
@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["one", "two", "three"])
async def test_any_listed_key_passes(monkeypatch, ok_processing, key):
    monkeypatch.setattr(settings, "API_KEY", "one, two,three")
    assert (await _post({"X-API-Key": key})).status_code == 200


# #UFB-0056
@pytest.mark.asyncio
async def test_key_compared_with_compare_digest(monkeypatch, ok_processing):
    monkeypatch.setattr(settings, "API_KEY", "secret")
    with patch("app.api_security.hmac.compare_digest", return_value=True) as cd:
        assert (await _post({"X-API-Key": "x"})).status_code == 200
    cd.assert_called()


# #UFB-0056
@pytest.mark.asyncio
async def test_health_needs_no_key(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "secret")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        assert (await ac.get("/healthz")).status_code == 200
        assert (await ac.get("/health")).status_code != 401


# #UFB-0056
def test_startup_warning_when_key_unset(caplog):
    with caplog.at_level("WARNING"):
        api_security.warn_if_open()
    assert "API_KEY" in caplog.text


# #UFB-0056
def test_no_startup_warning_when_key_set(monkeypatch, caplog):
    monkeypatch.setattr(settings, "API_KEY", "secret")
    with caplog.at_level("WARNING"):
        api_security.warn_if_open()
    assert "API_KEY" not in caplog.text


# --- rate limit ---


# #UFB-0056
@pytest.mark.asyncio
async def test_over_limit_is_429_with_retry_after(monkeypatch, ok_processing):
    monkeypatch.setattr(settings, "API_RATE_LIMIT", 2)
    assert (await _post()).status_code == 200
    assert (await _post()).status_code == 200
    response = await _post()
    assert response.status_code == 429
    assert 1 <= int(response.headers["Retry-After"]) <= settings.API_RATE_WINDOW


# #UFB-0056
@pytest.mark.asyncio
async def test_clients_are_limited_separately(monkeypatch, ok_processing):
    monkeypatch.setattr(settings, "API_RATE_LIMIT", 1)
    assert (await _post(client=("203.0.113.1", 1))).status_code == 200
    assert (await _post(client=("203.0.113.1", 1))).status_code == 429
    assert (await _post(client=("203.0.113.2", 1))).status_code == 200


# #UFB-0056
@pytest.mark.asyncio
async def test_zero_limit_disables(monkeypatch, ok_processing):
    monkeypatch.setattr(settings, "API_RATE_LIMIT", 0)
    for _ in range(5):
        assert (await _post()).status_code == 200


# #UFB-0056
@pytest.mark.asyncio
async def test_bad_key_attempts_count_toward_limit(monkeypatch, ok_processing):
    monkeypatch.setattr(settings, "API_KEY", "secret")
    monkeypatch.setattr(settings, "API_RATE_LIMIT", 1)
    assert (await _post({"X-API-Key": "a"})).status_code == 401
    assert (await _post({"X-API-Key": "b"})).status_code == 429


# #UFB-0056
def test_window_expires():
    limiter = api_security.RateLimiter()
    with patch("app.api_security.time.monotonic", return_value=100.0):
        assert limiter.check("c", 1, 60) is None
        assert limiter.check("c", 1, 60) == 60
    with patch("app.api_security.time.monotonic", return_value=130.0):
        assert limiter.check("c", 1, 60) == 30
    with patch("app.api_security.time.monotonic", return_value=161.0):
        assert limiter.check("c", 1, 60) is None


# --- client address ---


# #UFB-0056
@pytest.mark.parametrize(
    "peer,xff,trusted,expected",
    [
        ("203.0.113.9", "1.2.3.4", "", "203.0.113.9"),
        ("203.0.113.9", "1.2.3.4", "10.0.0.1", "203.0.113.9"),
        ("10.0.0.1", "1.2.3.4", "10.0.0.1", "1.2.3.4"),
        ("10.0.0.7", "1.2.3.4", "10.0.0.0/24", "1.2.3.4"),
        ("10.0.0.1", "6.6.6.6, 1.2.3.4", "10.0.0.1", "1.2.3.4"),
        ("10.0.0.1", "1.2.3.4, 10.0.0.2", "10.0.0.0/24", "1.2.3.4"),
        ("10.0.0.1", None, "10.0.0.1", "10.0.0.1"),
        ("10.0.0.1", "garbage", "10.0.0.1", "10.0.0.1"),
    ],
)
def test_client_address(peer, xff, trusted, expected):
    assert api_security.client_address(peer, xff, trusted) == expected


# #UFB-0056
@pytest.mark.asyncio
async def test_forged_xff_from_untrusted_peer_does_not_evade_limit(
    monkeypatch, ok_processing
):
    monkeypatch.setattr(settings, "API_RATE_LIMIT", 1)
    assert (await _post({"X-Forwarded-For": "1.1.1.1"})).status_code == 200
    assert (await _post({"X-Forwarded-For": "2.2.2.2"})).status_code == 429


# #UFB-0056
@pytest.mark.asyncio
async def test_trusted_proxy_xff_separates_clients(monkeypatch, ok_processing):
    monkeypatch.setattr(settings, "API_RATE_LIMIT", 1)
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "203.0.113.9")
    assert (await _post({"X-Forwarded-For": "1.1.1.1"})).status_code == 200
    assert (await _post({"X-Forwarded-For": "2.2.2.2"})).status_code == 200
    assert (await _post({"X-Forwarded-For": "1.1.1.1"})).status_code == 429
