# api_test.py

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_process_url_returns_processed_data():
    with patch(
        "app.api.process_url_request",
        new=AsyncMock(return_value="[Watch](https://example.test/video.mp4)"),
    ) as mock_process:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/process_url/", json={"url": "https://tiktok.com/@user/video/1"}
            )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"] == "[Watch](https://example.test/video.mp4)"
    mock_process.assert_awaited_once_with("https://tiktok.com/@user/video/1")


@pytest.mark.asyncio
async def test_process_url_returns_400_on_exception():
    with patch(
        "app.api.process_url_request",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/process_url/", json={"url": "https://tiktok.com/@user/video/1"}
            )

    assert response.status_code == 400
    assert "boom" in response.json()["detail"]
