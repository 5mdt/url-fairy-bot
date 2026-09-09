# pages.py
# -*- coding: utf-8 -*-

import logging
import os
import shutil
from urllib.parse import quote

from jinja2 import Environment, PackageLoader, select_autoescape

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


# #UFB-0032, #UFB-0033
def render_watch_page(media_filename: str) -> str:
    basename = os.path.basename(media_filename)
    media_url = f"https://{settings.BASE_URL}/{quote(basename)}"
    template = _env.get_template("watch.html")
    return template.render(
        page_url=watch_page_url(media_filename),
        media_url=media_url,
        image_url=f"https://{settings.BASE_URL}/{PREVIEW_IMAGE_FILENAME}",
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


# #UFB-0033, #UFB-0034
def seed_static_pages() -> None:
    os.makedirs(settings.CACHE_DIR, exist_ok=True)
    _write_atomic(os.path.join(settings.CACHE_DIR, "index.html"), render_landing_page())
    _write_atomic(os.path.join(settings.CACHE_DIR, "404.html"), render_404_page())
    shutil.copyfile(
        os.path.join(_ASSETS_DIR, PREVIEW_IMAGE_FILENAME),
        os.path.join(settings.CACHE_DIR, PREVIEW_IMAGE_FILENAME),
    )
    shutil.copyfile(
        os.path.join(_ASSETS_DIR, SAMPLE_MEDIA_FILENAME),
        os.path.join(settings.CACHE_DIR, SAMPLE_MEDIA_FILENAME),
    )
    write_watch_page(SAMPLE_MEDIA_FILENAME)
    global pages_seeded
    pages_seeded = True
