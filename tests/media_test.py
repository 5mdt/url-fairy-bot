# media_test.py

import json
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from app import media
from app.config import settings


def _loudnorm_stderr(input_i="-50.90") -> bytes:
    block = {
        "input_i": input_i,
        "input_tp": "-30.10",
        "input_lra": "2.50",
        "input_thresh": "-61.20",
        "output_i": "-16.00",
        "output_tp": "-1.50",
        "output_lra": "2.10",
        "output_thresh": "-26.30",
        "normalization_type": "dynamic",
        "target_offset": "0.30",
    }
    return (
        b"[Parsed_loudnorm_0 @ 0x1] \n" + json.dumps(block, indent=4).encode() + b"\n"
    )


def _result(returncode=0, stderr=b""):
    return MagicMock(returncode=returncode, stderr=stderr, stdout=b"")


@pytest.fixture
def media_file(tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"original")
    return str(path)


@pytest.fixture(autouse=True)
def normalize_settings(monkeypatch):
    monkeypatch.setattr(settings, "AUDIO_NORMALIZE_ENABLED", True)
    monkeypatch.setattr(settings, "AUDIO_NORMALIZE_BELOW_LUFS", -40.0)


# --- measure_loudness ---


def test_measure_loudness_parses_loudnorm_json(media_file):
    with patch(
        "app.media.subprocess.run", return_value=_result(stderr=_loudnorm_stderr())
    ):
        result = media.measure_loudness(media_file)

    assert result["input_i"] == "-50.90"
    assert result["input_thresh"] == "-61.20"


def test_measure_loudness_none_when_ffmpeg_missing(media_file):
    with patch("app.media.subprocess.run", side_effect=FileNotFoundError):
        assert media.measure_loudness(media_file) is None


def test_measure_loudness_none_on_timeout(media_file):
    with patch(
        "app.media.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=120),
    ):
        assert media.measure_loudness(media_file) is None


def test_measure_loudness_none_on_nonzero_exit(media_file):
    with patch(
        "app.media.subprocess.run", return_value=_result(1, b"Invalid data found")
    ):
        assert media.measure_loudness(media_file) is None


def test_measure_loudness_none_on_unparsable_output(media_file):
    with patch(
        "app.media.subprocess.run", return_value=_result(stderr=b"no json here")
    ):
        assert media.measure_loudness(media_file) is None


def test_measure_loudness_none_when_input_i_missing(media_file):
    with patch(
        "app.media.subprocess.run", return_value=_result(stderr=b'{"input_tp": "-1"}')
    ):
        assert media.measure_loudness(media_file) is None


# --- normalize_if_quiet ---


def test_normalize_disabled_makes_no_ffmpeg_call(media_file, monkeypatch):
    monkeypatch.setattr(settings, "AUDIO_NORMALIZE_ENABLED", False)

    with patch("app.media.subprocess.run") as mock_run:
        media.normalize_if_quiet(media_file)

    mock_run.assert_not_called()


def test_normalize_loud_file_is_left_unchanged(media_file):
    with patch(
        "app.media.subprocess.run",
        return_value=_result(stderr=_loudnorm_stderr("-15.00")),
    ) as mock_run:
        media.normalize_if_quiet(media_file)

    assert mock_run.call_count == 1
    assert open(media_file, "rb").read() == b"original"


def test_normalize_silent_file_is_skipped(media_file):
    with patch(
        "app.media.subprocess.run",
        return_value=_result(stderr=_loudnorm_stderr("-inf")),
    ) as mock_run:
        media.normalize_if_quiet(media_file)

    assert mock_run.call_count == 1
    assert open(media_file, "rb").read() == b"original"


def test_normalize_quiet_file_runs_second_pass_and_replaces_file(media_file):
    calls = []

    def _run(cmd, **kwargs):
        calls.append(cmd)
        if len(calls) == 1:
            return _result(stderr=_loudnorm_stderr())
        with open(cmd[-1], "wb") as f:
            f.write(b"normalized")
        return _result()

    with patch("app.media.subprocess.run", side_effect=_run):
        media.normalize_if_quiet(media_file)

    second = calls[1]
    af = second[second.index("-af") + 1]
    assert "measured_I=-50.90" in af
    assert "measured_thresh=-61.20" in af
    assert "offset=0.30" in af
    assert "linear=true" in af
    assert second[second.index("-c:v") + 1] == "copy"
    assert second[second.index("-c:a") + 1] == "aac"
    assert second[second.index("-b:a") + 1] == "160k"
    assert second[second.index("-f") + 1] == "mp4"
    assert second[-1].endswith(".part")
    assert open(media_file, "rb").read() == b"normalized"
    assert not os.path.exists(second[-1])


def test_normalize_second_pass_failure_keeps_original_and_cleans_up(media_file):
    calls = []

    def _run(cmd, **kwargs):
        calls.append(cmd)
        if len(calls) == 1:
            return _result(stderr=_loudnorm_stderr())
        with open(cmd[-1], "wb") as f:
            f.write(b"half written")
        return _result(1, b"boom")

    with patch("app.media.subprocess.run", side_effect=_run):
        media.normalize_if_quiet(media_file)

    assert open(media_file, "rb").read() == b"original"
    assert not os.path.exists(calls[1][-1])


def test_normalize_second_pass_timeout_never_raises(media_file):
    calls = []

    def _run(cmd, **kwargs):
        calls.append(cmd)
        if len(calls) == 1:
            return _result(stderr=_loudnorm_stderr())
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=120)

    with patch("app.media.subprocess.run", side_effect=_run):
        media.normalize_if_quiet(media_file)

    assert open(media_file, "rb").read() == b"original"


def test_normalize_threshold_is_configurable(media_file, monkeypatch):
    monkeypatch.setattr(settings, "AUDIO_NORMALIZE_BELOW_LUFS", -60.0)

    with patch(
        "app.media.subprocess.run", return_value=_result(stderr=_loudnorm_stderr())
    ) as mock_run:
        media.normalize_if_quiet(media_file)

    assert mock_run.call_count == 1
