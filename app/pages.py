# pages.py
# -*- coding: utf-8 -*-

import logging
import mimetypes
import os
import shutil
from urllib.parse import quote

from jinja2 import Environment, PackageLoader, select_autoescape

from app import preview
from app.config import settings

logger = logging.getLogger(__name__)

_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
SAMPLE_MEDIA_FILENAME = "sample.mp4"
PREVIEW_IMAGE_FILENAME = "preview.png"

pages_seeded = False

_env = Environment(
    loader=PackageLoader("app", "templates"),
    autoescape=select_autoescape(),
)


# #UFB-0033
def _write_atomic(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp_path, path)


# #UFB-0032, #UFB-0033
def watch_page_path(media_filename: str) -> str:
    stem = os.path.splitext(os.path.basename(media_filename))[0]
    return os.path.join(settings.CACHE_DIR, "watch", f"{stem}.html")


# #UFB-0032, #UFB-0033
def watch_page_url(media_filename: str) -> str:
    stem = os.path.splitext(os.path.basename(media_filename))[0]
    return f"https://{settings.BASE_URL}/watch/{quote(stem)}.html"


# #UFB-0032
def _fits_inline_video(media_filename: str) -> bool:
    """Whether the media file is small enough for an inline og:video/
    twitter:player embed. A file that can't be stat'd (already swept,
    permission error) is treated as small, so a missing file never blocks
    the page from rendering."""
    basename = os.path.basename(media_filename)
    media_path = os.path.join(settings.CACHE_DIR, basename)
    try:
        size_mb = os.path.getsize(media_path) / (1024 * 1024)
    except OSError:
        return True
    return size_mb <= settings.INLINE_VIDEO_MAX_MB


# #UFB-0032, #UFB-0033, #UFB-0035
def render_watch_page(media_filename: str) -> str:
    basename = os.path.basename(media_filename)
    media_url = f"https://{settings.BASE_URL}/{quote(basename)}"
    video_type = mimetypes.guess_type(basename)[0] or "video/mp4"
    if os.path.exists(preview.preview_path(media_filename)):
        image_url = preview.preview_url(media_filename)
        image_type = "image/jpeg"
    else:
        image_url = f"https://{settings.BASE_URL}/{PREVIEW_IMAGE_FILENAME}"
        image_type = mimetypes.guess_type(PREVIEW_IMAGE_FILENAME)[0] or "image/png"
    template = _env.get_template("watch.html")
    return template.render(
        page_url=watch_page_url(media_filename),
        media_url=media_url,
        image_url=image_url,
        image_type=image_type,
        video_type=video_type,
        inline_video=_fits_inline_video(media_filename),
    )


# #UFB-0032, #UFB-0033
def write_watch_page(media_filename: str) -> str:
    path = watch_page_path(media_filename)
    _write_atomic(path, render_watch_page(media_filename))
    return path


# #UFB-0031
def render_landing_page() -> str:
    return _env.get_template("landing.html").render()


# #UFB-0031, #UFB-0033
def render_404_page() -> str:
    return _env.get_template("404.html").render()


# #UFB-0033
def _cached_media_filenames() -> list[str]:
    """Basenames of media files already sitting at the top level of
    CACHE_DIR (excluding the bundled preview image and any HTML files)."""
    try:
        names = os.listdir(settings.CACHE_DIR)
    except OSError as e:
        logger.warning(f"Failed to list {settings.CACHE_DIR}: {e}")
        return []
    return [
        name
        for name in names
        if os.path.isfile(os.path.join(settings.CACHE_DIR, name))
        and name != PREVIEW_IMAGE_FILENAME
        and not name.endswith(".html")
    ]


# #UFB-0033, #UFB-0034, #UFB-0035
def seed_static_pages() -> None:
    os.makedirs(settings.CACHE_DIR, exist_ok=True)
    _write_atomic(os.path.join(settings.CACHE_DIR, "index.html"), render_landing_page())
    _write_atomic(os.path.join(settings.CACHE_DIR, "404.html"), render_404_page())
    shutil.copyfile(
        os.path.join(_ASSETS_DIR, PREVIEW_IMAGE_FILENAME),
        os.path.join(settings.CACHE_DIR, PREVIEW_IMAGE_FILENAME),
    )
    sample_path = os.path.join(settings.CACHE_DIR, SAMPLE_MEDIA_FILENAME)
    shutil.copyfile(
        os.path.join(_ASSETS_DIR, SAMPLE_MEDIA_FILENAME),
        sample_path,
    )
    try:
        preview.generate_preview(sample_path)
    except OSError as e:
        logger.warning(f"Failed to generate sample preview: {e}")
    write_watch_page(SAMPLE_MEDIA_FILENAME)
    for filename in _cached_media_filenames():
        if filename == SAMPLE_MEDIA_FILENAME:
            continue
        try:
            write_watch_page(filename)
        except OSError as e:
            logger.warning(f"Failed to regenerate watch page for {filename}: {e}")
    global pages_seeded
    pages_seeded = True
