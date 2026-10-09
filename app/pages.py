# pages.py
# -*- coding: utf-8 -*-

import logging
import mimetypes
import os
import re
import shutil
from urllib.parse import quote

from jinja2 import Environment, PackageLoader, select_autoescape

from app import media, metadata, preview
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


# #UFB-0032, #UFB-0039
def gallery_image_url(media_filename: str, image_filename: str) -> str:
    """Public URL of a gallery image (CACHE_DIR/gallery/<stem>/NN.jpg)."""
    stem = os.path.splitext(os.path.basename(media_filename))[0]
    return (
        f"https://{settings.BASE_URL}/gallery/{quote(stem)}/"
        f"{quote(os.path.basename(image_filename))}"
    )


# #UFB-0039
def _gallery_image_urls_from_disk(media_filename: str) -> list[str]:
    stem = os.path.splitext(os.path.basename(media_filename))[0]
    try:
        names = sorted(os.listdir(os.path.join(settings.CACHE_DIR, "gallery", stem)))
    except OSError:
        return []
    return [
        gallery_image_url(media_filename, n)
        for n in names
        if n.lower().endswith(media.GALLERY_EXTS)
    ]


# #UFB-0032
def _fits_inline_video(media_filename: str) -> bool:
    """Whether the media file is small enough for an inline og:video/
    twitter:player/<video> embed. Telegram's Instant View fetches every
    body media resource server-side while building the article, so an
    oversized <video> doesn't just fail to autoplay — it fails the whole
    article with NO_MEDIA_FOUND (confirmed live; see UFB-0032). Above this
    threshold, both the og:video*/twitter:player tags and the body <video>
    are omitted in favor of the preview image. A file that can't be stat'd
    (already swept, permission error) is treated as small, so a missing
    file never blocks the page from rendering."""
    basename = os.path.basename(media_filename)
    media_path = os.path.join(settings.CACHE_DIR, basename)
    try:
        size_mb = os.path.getsize(media_path) / (1024 * 1024)
    except OSError:
        return True
    return size_mb <= settings.INLINE_VIDEO_MAX_MB


# #UFB-0041
def _description_paragraphs(description) -> list[list[str]]:
    """Blank-line separated paragraphs of single lines: Instant View ignores
    `white-space: pre-wrap`, so breaks are rendered as <p> and <br>."""
    if not isinstance(description, str):
        return []
    paragraphs = [
        [line.strip() for line in para.splitlines() if line.strip()]
        for para in re.split(r"\n\s*\n", description)
    ]
    return [lines for lines in paragraphs if lines]


# #UFB-0041
def _metadata_view(media_filename: str) -> dict | None:
    """The full-form metadata for the watch page template, or None."""
    record = metadata.read(media_filename)
    if not record:
        return None
    avatar = record.get("avatar_url")
    uploader_url = record.get("uploader_url")
    subtitles = record.get("subtitles")
    return {
        "title": record.get("title"),
        "uploader": record.get("uploader"),
        "uploader_url": uploader_url
        if isinstance(uploader_url, str) and uploader_url.startswith("https://")
        else None,
        "description": record.get("description"),
        "description_paragraphs": _description_paragraphs(record.get("description")),
        "avatar_url": avatar
        if isinstance(avatar, str) and avatar.startswith("https://")
        else None,
        "subtitles": [
            {
                "name": name,
                "url": metadata.subtitle_url(media_filename, name),
            }
            for name in (subtitles if isinstance(subtitles, list) else [])
            if isinstance(name, str)
        ],
    }


# #UFB-0032, #UFB-0033, #UFB-0035, #UFB-0039, #UFB-0041
def render_watch_page(
    media_filename: str, gallery_image_urls: list[str] | None = None
) -> str:
    """An audio file gets the audio/gallery page (#BUG-0079); its images are
    `gallery_image_urls`, or those found in the gallery dir when None."""
    basename = os.path.basename(media_filename)
    media_url = f"https://{settings.BASE_URL}/{quote(basename)}"
    video_type = mimetypes.guess_type(basename)[0] or "video/mp4"
    if os.path.exists(preview.preview_path(media_filename)):
        image_url = preview.preview_url(media_filename)
        image_type = "image/jpeg"
    else:
        image_url = f"https://{settings.BASE_URL}/{PREVIEW_IMAGE_FILENAME}"
        image_type = mimetypes.guess_type(PREVIEW_IMAGE_FILENAME)[0] or "image/png"
    audio_mode = (mimetypes.guess_type(basename)[0] or "").startswith("audio/")
    if audio_mode:
        if gallery_image_urls is None:
            gallery_image_urls = _gallery_image_urls_from_disk(media_filename)
        if gallery_image_urls:
            image_url = gallery_image_urls[0]
            image_type = mimetypes.guess_type(gallery_image_urls[0])[0] or "image/jpeg"
    template = _env.get_template("watch.html")
    return template.render(
        audio_mode=audio_mode,
        gallery_image_urls=gallery_image_urls or [],
        page_url=watch_page_url(media_filename),
        media_url=media_url,
        image_url=image_url,
        image_type=image_type,
        video_type=video_type,
        show_video_meta=_fits_inline_video(media_filename),
        meta=_metadata_view(media_filename),
    )


# #UFB-0032, #UFB-0033, #UFB-0039
def write_watch_page(
    media_filename: str, gallery_image_urls: list[str] | None = None
) -> str:
    path = watch_page_path(media_filename)
    _write_atomic(path, render_watch_page(media_filename, gallery_image_urls))
    return path


_IMG_MARKER_RE = re.compile(r"^\[\[img:([^\]]+)\]\]$")


# #UFB-0057
def reddit_page_path(stem: str) -> str:
    return os.path.join(settings.CACHE_DIR, "reddit", f"{stem}.html")


# #UFB-0057
def reddit_page_url(stem: str) -> str:
    return f"https://{settings.BASE_URL}/reddit/{quote(stem)}.html"


# #UFB-0057
def _reddit_blocks(section: dict) -> list[tuple[str, object]]:
    """`("p", lines)` / `("img", url)` blocks for a section's body. A
    `[[img:ID]]` line becomes the image cached for ID; images the text never
    mentions follow it."""
    images = section.get("images") or {}
    used = set()
    blocks: list[tuple[str, object]] = []
    for lines in _description_paragraphs(section.get("body")):
        match = _IMG_MARKER_RE.match(lines[0]) if len(lines) == 1 else None
        if not match:
            blocks.append(("p", lines))
        elif url := images.get(match.group(1)):
            used.add(match.group(1))
            blocks.append(("img", url))
    blocks.extend(("img", url) for key, url in images.items() if key not in used)
    return blocks


# #UFB-0057
def render_reddit_page(stem: str, view: dict) -> str:
    """`view`: `title`, `description`, `source_url`, optional `banner`, and
    `sections` (dicts with `heading`, `title`, `avatar`, `author`,
    `author_url`, `subreddit`, `subreddit_url`, `subtitle`, `body`,
    `images` {id: https URL})."""
    sections = [{**sec, "blocks": _reddit_blocks(sec)} for sec in view["sections"]]
    first_image = next(
        (block[1] for sec in sections for block in sec["blocks"] if block[0] == "img"),
        None,
    )
    og_image = first_image or view.get("banner")
    if not og_image:
        og_image = next((s["avatar"] for s in sections if s.get("avatar")), None)
    return _env.get_template("reddit.html").render(
        page_url=reddit_page_url(stem),
        page_title=view["title"],
        description=view.get("description") or "",
        og_image=og_image or f"https://{settings.BASE_URL}/{PREVIEW_IMAGE_FILENAME}",
        banner=view.get("banner"),
        sections=sections,
        source_url=view["source_url"],
    )


# #UFB-0057
def write_reddit_page(stem: str, view: dict) -> str:
    path = reddit_page_path(stem)
    _write_atomic(path, render_reddit_page(stem, view))
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
