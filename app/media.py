# media.py
# -*- coding: utf-8 -*-

import json
import logging
import subprocess

logger = logging.getLogger(__name__)

_PROBE_TIMEOUT_SECONDS = 10


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
