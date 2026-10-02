# media.py
# -*- coding: utf-8 -*-

import json
import logging
import math
import os
import re
import subprocess

from app.config import settings

logger = logging.getLogger(__name__)

_PROBE_TIMEOUT_SECONDS = 10
_LOUDNORM_TIMEOUT_SECONDS = 120
_LOUDNORM_TARGET = "I=-16:TP=-1.5:LRA=11"
# loudnorm's print_format=json block has no nested braces.
_JSON_BLOCK_RE = re.compile(r"\{[^{}]*\}")


# #UFB-0036
def probe(media_os_path: str) -> dict | None:
    """Probe `media_os_path` for width/height/duration via ffprobe. Returns
    None on any failure (missing binary, non-zero exit, timeout, unparsable
    output) — this never raises, since a failed probe must never break a
    video send; the caller just sends without those hints."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                media_os_path,
            ],
            capture_output=True,
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        logger.warning("ffprobe not found; skipping media probe")
        return None
    except subprocess.TimeoutExpired:
        logger.warning(f"ffprobe timed out probing {media_os_path}")
        return None

    if result.returncode != 0:
        logger.warning(
            f"ffprobe failed to probe {media_os_path}: "
            f"{result.stderr.decode(errors='replace').strip()}"
        )
        return None

    try:
        data = json.loads(result.stdout)
        stream = data["streams"][0]
        duration = data.get("format", {}).get("duration")
        return {
            "width": int(stream["width"]),
            "height": int(stream["height"]),
            "duration": int(float(duration)) if duration is not None else None,
        }
    except (KeyError, IndexError, ValueError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to parse ffprobe output for {media_os_path}: {e}")
        return None


# #UFB-0040
def measure_loudness(media_os_path: str) -> dict | None:
    """First loudnorm pass over `media_os_path`'s audio: the measured values
    (`input_i`, `input_tp`, `input_lra`, `input_thresh`, `target_offset`) as
    ffmpeg prints them. Returns None on any failure (missing binary, timeout,
    non-zero exit incl. no audio stream, unparsable output); never raises."""
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-i",
                media_os_path,
                "-vn",
                "-af",
                f"loudnorm={_LOUDNORM_TARGET}:print_format=json",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            timeout=_LOUDNORM_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        logger.warning("ffmpeg not found; skipping loudness measurement")
        return None
    except subprocess.TimeoutExpired:
        logger.warning(f"ffmpeg timed out measuring loudness of {media_os_path}")
        return None

    stderr = result.stderr.decode(errors="replace")
    if result.returncode != 0:
        logger.warning(
            f"ffmpeg failed to measure loudness of {media_os_path}: {stderr.strip()[-300:]}"
        )
        return None

    blocks = _JSON_BLOCK_RE.findall(stderr)
    try:
        data = json.loads(blocks[-1])
        if "input_i" not in data:
            raise KeyError("input_i")
        return data
    except (IndexError, KeyError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to parse loudness of {media_os_path}: {e}")
        return None


# #UFB-0040
def normalize_if_quiet(media_os_path: str) -> None:
    """If enabled and the file's integrated loudness is below
    `AUDIO_NORMALIZE_BELOW_LUFS`, normalize its audio to -16 LUFS in place
    (video stream copied). Never raises: any failure leaves the original
    file untouched."""
    if not settings.AUDIO_NORMALIZE_ENABLED:
        return

    measured = measure_loudness(media_os_path)
    if measured is None:
        return

    try:
        loudness = float(measured["input_i"])
    except TypeError, ValueError:
        logger.warning(f"Unusable loudness for {media_os_path}: {measured}")
        return
    if not math.isfinite(loudness):
        logger.info(f"Audio of {media_os_path} is silent; not normalizing")
        return
    if loudness >= settings.AUDIO_NORMALIZE_BELOW_LUFS:
        return

    try:
        loudnorm = (
            f"loudnorm={_LOUDNORM_TARGET}"
            f":measured_I={measured['input_i']}"
            f":measured_TP={measured['input_tp']}"
            f":measured_LRA={measured['input_lra']}"
            f":measured_thresh={measured['input_thresh']}"
            f":offset={measured['target_offset']}"
            ":linear=true"
        )
    except KeyError as e:
        logger.warning(f"Incomplete loudness data for {media_os_path}: missing {e}")
        return

    # `.part` keeps download._cached_media_path from treating a half-written
    # file as a finished download.
    tmp_path = f"{media_os_path}.loudnorm.part"
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-y",
                "-i",
                media_os_path,
                "-map",
                "0:v?",
                "-map",
                "0:a",
                "-c:v",
                "copy",
                "-af",
                loudnorm,
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                "-movflags",
                "+faststart",
                "-f",
                "mp4",
                tmp_path,
            ],
            capture_output=True,
            timeout=_LOUDNORM_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            logger.warning(
                f"ffmpeg failed to normalize {media_os_path}: "
                f"{result.stderr.decode(errors='replace').strip()[-300:]}"
            )
            return
        os.replace(tmp_path, media_os_path)
        logger.info(f"Normalized audio of {media_os_path} (was {loudness} LUFS)")
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        logger.warning(f"Failed to normalize {media_os_path}: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
