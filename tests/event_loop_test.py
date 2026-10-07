# event_loop_test.py
#
# #BUG-0006: blocking network/CPU calls must run off the asyncio event loop.
# Each test runs a slow *blocking* stand-in for the real call next to a
# ticker task; if the call ran on the loop, the ticker would not tick.

import asyncio
import os
import time
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.bot import _reply_with_video
from app.config import settings
from app.download import url_to_filename_stem, yt_dlp_download
from app.url_processing import attempt_download, process_url_request

BLOCK_SECONDS = 0.3
MIN_TICKS = 5  # 10ms ticker over 300ms; a blocked loop yields ~0-1


def _slow(*_args, **_kwargs):
    time.sleep(BLOCK_SECONDS)


@asynccontextmanager
async def _ticker():
    """Yields a list that a background task appends to every 10ms."""
    ticks: list[float] = []

    async def tick():
        while True:
            ticks.append(time.monotonic())
            await asyncio.sleep(0.01)

    task = asyncio.create_task(tick())
    await asyncio.sleep(0)  # let it take its first tick
    try:
        yield ticks
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# #BUG-0006
@pytest.mark.asyncio
async def test_follow_redirects_does_not_block_loop():
    def slow_follow(url):
        _slow()
        return url

    with patch("app.url_processing.follow_redirects", side_effect=slow_follow):
        async with _ticker() as ticks:
            await process_url_request("https://example.com/x", is_group_chat=True)
    assert len(ticks) >= MIN_TICKS


# #BUG-0006
@pytest.mark.asyncio
async def test_ydl_download_and_normalize_do_not_block_loop(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "COOKIES_DIR", str(tmp_path))
    url = "https://tiktok.com/@user/video/loop"
    out = os.path.join(str(tmp_path), f"{url_to_filename_stem(url)}.mp4")

    def slow_download(_url, download=True):
        _slow()
        with open(out, "w") as f:
            f.write("data")

    mock_ydl = MagicMock()
    mock_ydl.__enter__.return_value.extract_info.side_effect = slow_download
    with (
        patch("app.download.yt_dlp.YoutubeDL", return_value=mock_ydl),
        patch("app.download.media.normalize_if_quiet", side_effect=_slow),
    ):
        async with _ticker() as ticks:
            assert await yt_dlp_download(url) == out
    # Both the download and the normalize pass (2 x BLOCK_SECONDS) stayed off the loop.
    assert len(ticks) >= 2 * MIN_TICKS


# #BUG-0006
@pytest.mark.asyncio
async def test_generate_preview_does_not_block_loop(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    with (
        patch("app.url_processing.yt_dlp_download", AsyncMock(return_value=str(video))),
        patch("app.url_processing.preview.generate_preview", side_effect=_slow),
        patch("app.url_processing.pages.write_watch_page"),
    ):
        async with _ticker() as ticks:
            result = await attempt_download("https://tiktok.com/@user/video/1")
    assert result is not None
    assert len(ticks) >= MIN_TICKS


# #BUG-0006
@pytest.mark.asyncio
async def test_probe_does_not_block_loop(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"0")
    message = MagicMock()
    message.reply_video = AsyncMock()
    with patch("app.bot.media.probe", side_effect=_slow):
        async with _ticker() as ticks:
            assert await _reply_with_video(message, str(clip), "c") is True
    assert len(ticks) >= MIN_TICKS
