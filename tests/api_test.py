# api_test.py

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.url_processing import BlockedUrlError, DownloadResult


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
async def test_process_url_unwraps_download_result_text():
    result = DownloadResult(
        text="[Watch](https://example.test/video.mp4)", media_path="/cache/video.mp4"
    )
    with patch("app.api.process_url_request", new=AsyncMock(return_value=result)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/process_url/", json={"url": "https://tiktok.com/@user/video/1"}
            )

    body = response.json()
    assert body["status"] == "success"
    assert body["data"] == "[Watch](https://example.test/video.mp4)"


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


# #BUG-0012, #UFB-0019
@pytest.mark.asyncio
async def test_process_url_rejects_non_url_with_422_before_processing():
    with patch("app.api.process_url_request", new=AsyncMock()) as mock_process:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post("/process_url/", json={"url": "not a url"})

    assert response.status_code == 422
    mock_process.assert_not_awaited()


# #BUG-0012
@pytest.mark.asyncio
async def test_process_url_blocked_target_returns_400_generic():
    with patch(
        "app.api.process_url_request",
        new=AsyncMock(side_effect=BlockedUrlError("secret 10.0.0.1 detail")),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post("/process_url/", json={"url": "http://10.0.0.1/"})

    assert response.status_code == 400
    assert "10.0.0.1" not in response.json()["detail"]


# #BUG-0012
@pytest.mark.asyncio
async def test_process_url_end_to_end_private_target_makes_no_request():
    with patch("requests.head") as head:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/process_url/", json={"url": "http://169.254.169.254/latest/"}
            )

    assert response.status_code == 400
    head.assert_not_called()
