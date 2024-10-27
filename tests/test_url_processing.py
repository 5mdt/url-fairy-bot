# test_url_processing.py

import os
import pytest
from unittest.mock import patch, AsyncMock
from app.url_processing import process_url_request, transform_tiktok_url

@pytest.mark.asyncio
async def test_tiktok_url_processing():
    test_url = "https://vt.tiktok.com/ZSYFmgDeS/"
    expected_file_path = "/tmp/url-fairy-bot-cache/https___www_tiktok_com___video_7371578973689482539.mp4"
    transformed_url = transform_tiktok_url("https://www.tiktok.com/video/7371578973689482539")

    # Mock follow_redirects to return the final TikTok URL format
    with patch("app.url_processing.follow_redirects", return_value="https://www.tiktok.com/video/7371578973689482539"):
        # Mock yt_dlp_download to simulate successful download
        with patch("app.url_processing.yt_dlp_download", return_value=expected_file_path) as mock_download:
            result = await process_url_request(test_url)

            # Assertions
            mock_download.assert_called_once_with(transformed_url)
            assert result == expected_file_path
