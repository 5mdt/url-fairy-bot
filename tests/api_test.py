# api_test.py

import pytest
from httpx import AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_process_url():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/process_url/", json={"url": "https://example.com"})
    assert response.status_code == 200
    assert response.json()["status"] == "success"
