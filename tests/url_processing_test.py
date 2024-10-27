# url_processing_test.py

from unittest.mock import patch

import pytest

from app.config import settings
from app.url_processing import process_url_request


@pytest.mark.asyncio
async def test_tiktok_url_processing():
    test_url = "https://vt.tiktok.com/ZSYFmgDeS/"
    expected_file_path = "/tmp/url-fairy-bot-cache/https___www_tiktok_com___video_7371578973689482539.mp4"
    # Mock follow_redirects to return the final TikTok URL format
    with patch(
        "app.url_processing.follow_redirects",
        return_value="https://www.tiktok.com/video/7371578973689482539",
    ):
        # Mock yt_dlp_download to simulate successful download
        with patch(
            "app.url_processing.yt_dlp_download", return_value=expected_file_path
        ) as mock_download:
            result = await process_url_request(test_url)

            # Assertions
            mock_download.assert_called_once_with(
                "https://www.tiktok.com/video/7371578973689482539"
            )
            assert result == f"https://{settings.BASE_URL}{expected_file_path}"
