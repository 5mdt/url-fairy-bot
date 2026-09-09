# preview_test.py

import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from app import preview
from app.config import settings


@pytest.fixture(autouse=True)
def cache_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    return tmp_path


# --- preview_path / preview_url ---


def test_preview_path_maps_media_filename_to_preview_subdir(cache_dir):
    assert preview.preview_path("x.mp4") == str(cache_dir / "preview" / "x.jpg")


def test_preview_url_maps_media_filename_to_jpg_url():
    assert preview.preview_url("x.mp4") == "https://example.test/preview/x.jpg"


def test_preview_url_percent_encodes_the_stem():
    url = preview.preview_url("some video (1).mp4")
    assert url == "https://example.test/preview/some%20video%20%281%29.jpg"


# --- generate_preview ---


def _fake_run_success(tmp_path_dest):
    def _run(cmd, **kwargs):
        # ffmpeg's destination is always the last argument.
        with open(cmd[-1], "wb") as f:
            f.write(b"fake jpeg data")
        return MagicMock(returncode=0)

    return _run


def test_generate_preview_invokes_ffmpeg_and_writes_destination(cache_dir):
    media_path = str(cache_dir / "clip.mp4")
    with open(media_path, "w") as f:
        f.write("fake video data")

    with patch("app.preview.subprocess.run") as mock_run:
        mock_run.side_effect = _fake_run_success(cache_dir)
        result = preview.generate_preview(media_path)

    assert result == str(cache_dir / "preview" / "clip.jpg")
    assert os.path.isfile(result)
    args, kwargs = mock_run.call_args
    argv = args[0]
    assert argv[0] == "ffmpeg"
    assert "-i" in argv and media_path in argv
    assert kwargs.get("timeout")


def test_generate_preview_leaves_no_tmp_file_on_success(cache_dir):
    media_path = str(cache_dir / "clip.mp4")
    with open(media_path, "w") as f:
        f.write("data")

    with patch("app.preview.subprocess.run") as mock_run:
        mock_run.side_effect = _fake_run_success(cache_dir)
        preview.generate_preview(media_path)

    assert list((cache_dir / "preview").glob("*.tmp")) == []


def test_generate_preview_retries_at_zero_seconds_before_giving_up(cache_dir):
    media_path = str(cache_dir / "clip.mp4")
    with open(media_path, "w") as f:
        f.write("data")

    calls = []

    def _run(cmd, **kwargs):
        calls.append(cmd)
        if len(calls) == 1:
            return MagicMock(returncode=1)
        with open(cmd[-1], "wb") as f:
            f.write(b"fake jpeg data")
        return MagicMock(returncode=0)

    with patch("app.preview.subprocess.run", side_effect=_run):
        result = preview.generate_preview(media_path)

    assert result == str(cache_dir / "preview" / "clip.jpg")
    assert len(calls) == 2


def test_generate_preview_returns_none_on_persistent_failure(cache_dir):
    media_path = str(cache_dir / "clip.mp4")
    with open(media_path, "w") as f:
        f.write("data")

    with patch("app.preview.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        result = preview.generate_preview(media_path)

    assert result is None


def test_generate_preview_returns_none_when_ffmpeg_missing(cache_dir):
    media_path = str(cache_dir / "clip.mp4")
    with open(media_path, "w") as f:
        f.write("data")

    with patch("app.preview.subprocess.run", side_effect=FileNotFoundError):
        result = preview.generate_preview(media_path)

    assert result is None


def test_generate_preview_returns_none_on_timeout(cache_dir):
    media_path = str(cache_dir / "clip.mp4")
    with open(media_path, "w") as f:
        f.write("data")

    with patch(
        "app.preview.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=10),
    ):
        result = preview.generate_preview(media_path)

    assert result is None
