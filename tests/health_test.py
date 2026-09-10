# health_test.py

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app import api as api_module
from app import bot as bot_module
from app import cleanup as cleanup_module
from app import pages as pages_module
from app.main import app


@pytest.mark.asyncio
async def test_healthz_always_ok():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_ok_when_polling_seeded_and_cleanup_alive(monkeypatch):
    async def never_ends():
        await asyncio.Event().wait()

    task = asyncio.create_task(never_ends())
    monkeypatch.setattr(bot_module, "polling_task", task)
    monkeypatch.setattr(pages_module, "pages_seeded", True)
    monkeypatch.setattr(cleanup_module, "is_cleanup_alive", lambda: True)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health")

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "status": "ok",
        "polling": True,
        "pages_seeded": True,
        "cleanup": True,
        "telegram_api": None,
    }


@pytest.mark.asyncio
async def test_health_degraded_when_no_polling_task(monkeypatch):
    monkeypatch.setattr(bot_module, "polling_task", None)
    monkeypatch.setattr(pages_module, "pages_seeded", True)
    monkeypatch.setattr(cleanup_module, "is_cleanup_alive", lambda: True)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["polling"] is False


@pytest.mark.asyncio
async def test_health_degraded_when_polling_task_done(monkeypatch):
    async def finished():
        return None

    task = asyncio.create_task(finished())
    await task
    monkeypatch.setattr(bot_module, "polling_task", task)
    monkeypatch.setattr(pages_module, "pages_seeded", True)
    monkeypatch.setattr(cleanup_module, "is_cleanup_alive", lambda: True)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health")

    assert response.status_code == 503
    assert response.json()["polling"] is False


@pytest.mark.asyncio
async def test_health_degraded_when_pages_not_seeded(monkeypatch):
    async def never_ends():
        await asyncio.Event().wait()

    task = asyncio.create_task(never_ends())
    monkeypatch.setattr(bot_module, "polling_task", task)
    monkeypatch.setattr(pages_module, "pages_seeded", False)
    monkeypatch.setattr(cleanup_module, "is_cleanup_alive", lambda: True)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health")

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert response.status_code == 503
    body = response.json()
    assert body["pages_seeded"] is False


@pytest.mark.asyncio
async def test_health_degraded_when_cleanup_not_alive(monkeypatch):
    async def never_ends():
        await asyncio.Event().wait()

    task = asyncio.create_task(never_ends())
    monkeypatch.setattr(bot_module, "polling_task", task)
    monkeypatch.setattr(pages_module, "pages_seeded", True)
    monkeypatch.setattr(cleanup_module, "is_cleanup_alive", lambda: False)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health")

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert response.status_code == 503
    body = response.json()
    assert body["cleanup"] is False


# --- UFB-0036: telegram_api reachability ---


@pytest.mark.asyncio
async def test_health_ok_when_telegram_api_url_unset(monkeypatch):
    """TELEGRAM_API_URL unset (the default) → nothing to check, must not
    degrade health."""

    async def never_ends():
        await asyncio.Event().wait()

    task = asyncio.create_task(never_ends())
    monkeypatch.setattr(bot_module, "polling_task", task)
    monkeypatch.setattr(pages_module, "pages_seeded", True)
    monkeypatch.setattr(cleanup_module, "is_cleanup_alive", lambda: True)
    monkeypatch.setattr(api_module, "is_telegram_api_reachable", lambda: None)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health")

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert response.status_code == 200
    assert response.json()["telegram_api"] is None


@pytest.mark.asyncio
async def test_health_ok_when_telegram_api_reachable(monkeypatch):
    async def never_ends():
        await asyncio.Event().wait()

    task = asyncio.create_task(never_ends())
    monkeypatch.setattr(bot_module, "polling_task", task)
    monkeypatch.setattr(pages_module, "pages_seeded", True)
    monkeypatch.setattr(cleanup_module, "is_cleanup_alive", lambda: True)
    monkeypatch.setattr(api_module, "is_telegram_api_reachable", lambda: True)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health")

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert response.status_code == 200
    assert response.json()["telegram_api"] is True


@pytest.mark.asyncio
async def test_health_degraded_when_telegram_api_configured_but_unreachable(
    monkeypatch,
):
    async def never_ends():
        await asyncio.Event().wait()

    task = asyncio.create_task(never_ends())
    monkeypatch.setattr(bot_module, "polling_task", task)
    monkeypatch.setattr(pages_module, "pages_seeded", True)
    monkeypatch.setattr(cleanup_module, "is_cleanup_alive", lambda: True)
    monkeypatch.setattr(api_module, "is_telegram_api_reachable", lambda: False)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health")

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["telegram_api"] is False
