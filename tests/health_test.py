# health_test.py

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app import bot as bot_module
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
async def test_health_ok_when_polling_and_seeded(monkeypatch):
    async def never_ends():
        await asyncio.Event().wait()

    task = asyncio.create_task(never_ends())
    monkeypatch.setattr(bot_module, "polling_task", task)
    monkeypatch.setattr(pages_module, "pages_seeded", True)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health")

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok", "polling": True, "pages_seeded": True}


@pytest.mark.asyncio
async def test_health_degraded_when_no_polling_task(monkeypatch):
    monkeypatch.setattr(bot_module, "polling_task", None)
    monkeypatch.setattr(pages_module, "pages_seeded", True)

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
