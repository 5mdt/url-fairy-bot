# preview.py
# -*- coding: utf-8 -*-

import logging
import os
import subprocess
from urllib.parse import quote

from app.config import settings

logger = logging.getLogger(__name__)

_PREVIEW_TIMEOUT_SECONDS = 10
# Seek offsets to try, in order: 1s avoids a black opening frame on most
# clips; 0s is the fallback for anything shorter than that.
_PREVIEW_SEEK_OFFSETS = ("1", "0")


# #UFB-0035
def preview_path(media_filename: str) -> str:
    stem = os.path.splitext(os.path.basename(media_filename))[0]
    return os.path.join(settings.CACHE_DIR, "preview", f"{stem}.jpg")


# #UFB-0035
def preview_url(media_filename: str) -> str:
    stem = os.path.splitext(os.path.basename(media_filename))[0]
    return f"https://{settings.BASE_URL}/preview/{quote(stem)}.jpg"


# #UFB-0035
def generate_preview(media_os_path: str) -> str | None:
    """Extract one JPEG frame from `media_os_path` via ffmpeg and write it
    atomically to its preview path. Returns the destination path on
    success, or None on any failure (missing binary, non-zero exit,
    timeout) — this never raises, since a missing preview must never break
    a download."""
    dest = preview_path(os.path.basename(media_os_path))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp_path = f"{dest}.tmp"

    for seek in _PREVIEW_SEEK_OFFSETS:
        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    seek,
                    "-i",
                    media_os_path,
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=1200:-2",
                    "-q:v",
                    "3",
                    # Force the muxer explicitly: the atomic write's `.tmp`
                    # suffix (below) means ffmpeg can't infer a JPEG from the
                    # filename extension and otherwise refuses to write
                    # anything (#BUG-0066).
                    "-f",
                    "mjpeg",
                    tmp_path,
                ],
                capture_output=True,
                timeout=_PREVIEW_TIMEOUT_SECONDS,
            )
        except FileNotFoundError:
            logger.warning("ffmpeg not found; skipping preview generation")
            return None
        except subprocess.TimeoutExpired:
            logger.warning(f"ffmpeg timed out generating preview for {media_os_path}")
            return None

        if result.returncode == 0 and os.path.exists(tmp_path):
            os.replace(tmp_path, dest)
            return dest

    logger.warning(
        f"ffmpeg failed to generate preview for {media_os_path}: "
        f"{result.stderr.decode(errors='replace').strip()}"
    )
    return None
