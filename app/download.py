# download.py
# -*- coding: utf-8 -*-

import asyncio
import glob
import hashlib
import logging
import os
import re
import tempfile
import threading
import time
from contextlib import asynccontextmanager, contextmanager, nullcontext
from dataclasses import dataclass

import yt_dlp

from app import media, metrics
from app.config import settings

logger = logging.getLogger(__name__)

COOKIE_JAR_PATH = os.path.join(settings.COOKIES_DIR, "cookie_jar.txt")

# #UFB-0038: yt-dlp (jar mode) and the cookie keepalive both write the jar.
COOKIE_JAR_LOCK = threading.Lock()


# #UFB-0013
class UnsupportedUrlError(Exception):
    """Custom exception for unsupported URLs"""

    pass


# #UFB-0017
def _write_merged_cookies(dest: str, cookie_files: list[str]) -> None:
    with open(dest, "w", encoding="utf-8") as out:
        out.write("# Netscape HTTP Cookie File\n")
        for path in cookie_files:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        # Drop real comments ("# ..." or a bare "#") but keep
                        # a single "#" with no space: Netscape jars mark
                        # HttpOnly cookies as "#HttpOnly_<domain>\t...", and
                        # those are data lines yt-dlp must still read.
                        if not line.startswith("# ") and line.strip() != "#":
                            out.write(line)
            except Exception as e:
                logger.warning(f"Failed to read cookies file {path}: {e}")


# #UFB-0018, #UFB-0038
def cookie_sources_sidecar_path() -> str:
    """Records the newest source-file mtime the jar was last merged from."""
    return os.path.splitext(COOKIE_JAR_PATH)[0] + ".sources"


# #UFB-0018, #UFB-0038
def write_cookie_jar(cookie_files: list[str]) -> None:
    """(Re)build the jar from the source files and remember how fresh they were."""
    _write_merged_cookies(COOKIE_JAR_PATH, cookie_files)
    try:
        newest = max(os.path.getmtime(p) for p in cookie_files)
        with open(cookie_sources_sidecar_path(), "w", encoding="utf-8") as f:
            f.write(repr(newest))
    except (OSError, ValueError) as e:
        logger.warning(f"Failed to record cookie source mtime: {e}")


# #UFB-0017, #UFB-0018
def _resolve_cookie_path(cookie_files: list[str]) -> tuple[str, bool]:
    """Returns (cookie_file_path, should_delete_after)."""
    if settings.COOKIE_JAR_ENABLED:
        if not os.path.exists(COOKIE_JAR_PATH):
            logger.info(f"Initializing cookie jar from: {cookie_files}")
            write_cookie_jar(cookie_files)
        else:
            logger.info(f"Using existing cookie jar: {COOKIE_JAR_PATH}")
        return COOKIE_JAR_PATH, False

    tmp = tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".txt", encoding="utf-8"
    )
    tmp.close()
    _write_merged_cookies(tmp.name, cookie_files)
    logger.info(f"Using merged temp cookies from: {cookie_files}")
    return tmp.name, True


# #UFB-0026
def _touch_atime(path: str) -> None:
    """Mark a cache hit as a touch so it isn't swept as stale."""
    try:
        st = os.stat(path)
        os.utime(path, (time.time(), st.st_mtime))
    except OSError as e:
        logger.warning(f"Failed to refresh atime for {path}: {e}")


# Leftover fragments from an interrupted yt-dlp download; never a finished file.
_INCOMPLETE_SUFFIXES = (".part", ".ytdl")


# #UFB-0015
def _cached_media_path(stem: str) -> str | None:
    """The cached media file for `stem`, at whatever real extension it was
    actually saved with (#BUG-0015: no longer assumed to be `.mp4`), or
    None if nothing finished downloading for it yet."""
    for match in glob.glob(os.path.join(settings.CACHE_DIR, f"{stem}.*")):
        if not match.endswith(_INCOMPLETE_SUFFIXES):
            return match
    return None


# #UFB-0015, #UFB-0017, #UFB-0038, #UFB-0039
@contextmanager
def _youtube_dl(ydl_opts: dict):
    """A YoutubeDL configured with the merged cookies, if any. With the jar
    enabled, the jar lock is held for the whole block (#UFB-0038); a
    temporary merged cookie file is removed afterwards."""
    cookie_files = glob.glob(os.path.join(settings.COOKIES_DIR, "cookies*.txt"))
    if not cookie_files:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            yield ydl
        return

    # #UFB-0038: serialize jar init + download against the keepalive.
    guard = COOKIE_JAR_LOCK if settings.COOKIE_JAR_ENABLED else nullcontext()
    with guard:
        cookie_path, should_delete = _resolve_cookie_path(cookie_files)
        ydl_opts["cookiefile"] = cookie_path
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                yield ydl
        finally:
            if should_delete:
                try:
                    os.unlink(cookie_path)
                except Exception:
                    pass


# #UFB-0013, #UFB-0015, #UFB-0039
def _map_download_errors(url: str, e: Exception) -> Exception:
    """The exception `yt_dlp_download`-style callers raise for `e`."""
    if isinstance(e, yt_dlp.DownloadError):
        if "Unsupported URL" in str(e):
            logger.error(f"Unsupported URL: {url}")
            return UnsupportedUrlError(f"Unsupported URL: {url}")
        logger.error(f"DownloadError for URL: {url} - {str(e)}")
        return RuntimeError(
            f"Failed to download video from URL: {url}. Check if the URL is correct and accessible."
        )
    if isinstance(e, yt_dlp.utils.PostProcessingError):
        logger.error(f"PostProcessingError for URL: {url} - {str(e)}")
        return RuntimeError(
            f"An error occurred while processing the video file for URL: {url}."
        )
    logger.error(f"Unexpected error for URL: {url} - {str(e)}")
    return RuntimeError(
        f"An unexpected error occurred while processing the URL: {url}. Please try again later."
    )


# #BUG-0014: per-stem locks; entries are dropped once nobody holds/awaits them.
_URL_LOCKS: dict[str, tuple[asyncio.Lock, int]] = {}


# #UFB-0016, #BUG-0014
@asynccontextmanager
async def _url_lock(stem: str):
    """Serialize the cache check + download for one URL stem."""
    lock, users = _URL_LOCKS.get(stem, (None, 0))
    lock = lock or asyncio.Lock()
    _URL_LOCKS[stem] = (lock, users + 1)
    try:
        async with lock:
            yield
    finally:
        lock, users = _URL_LOCKS[stem]
        if users <= 1:
            del _URL_LOCKS[stem]
        else:
            _URL_LOCKS[stem] = (lock, users - 1)


# #BUG-0006, #UFB-0015
def _run_ydl_download(ydl_opts: dict, url: str) -> None:
    """The blocking yt-dlp download, including the cookie setup and the jar
    lock acquisition (#UFB-0038); always called via asyncio.to_thread."""
    with _youtube_dl(ydl_opts) as ydl:
        ydl.download([url])


# #UFB-0015, #UFB-0016, #UFB-0017, #UFB-0040, #BUG-0014
async def yt_dlp_download(url: str) -> str:
    stem = url_to_filename_stem(url)
    async with _url_lock(stem):
        return await _yt_dlp_download_locked(url, stem)


# #UFB-0015, #UFB-0016, #UFB-0017, #UFB-0040, #BUG-0014
async def _yt_dlp_download_locked(url: str, stem: str) -> str:
    cached_path = _cached_media_path(stem)

    if cached_path:
        logger.info(f"File already exists for URL: {url}, skipping download.")
        _touch_atime(cached_path)
        metrics.record_cache(hit=True)  # #UFB-0045
        return cached_path

    metrics.record_cache(hit=False)  # #UFB-0045

    try:
        ydl_opts = {
            "outtmpl": os.path.join(settings.CACHE_DIR, f"{stem}.%(ext)s"),
            "format": "best",
            # Losslessly repackage a compatible non-mp4 container into a
            # real .mp4 instead of leaving the file mislabeled (#BUG-0015).
            "merge_output_format": "mp4",
            "postprocessors": [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}],
        }
        await asyncio.to_thread(_run_ydl_download, ydl_opts, url)

        logger.info(f"Download successful for URL: {url}")
        path = _cached_media_path(stem)
        if path:
            await asyncio.to_thread(media.normalize_if_quiet, path)
            metrics.record_downloader("yt-dlp")  # #UFB-0045
        return path

    except Exception as e:
        mapped = _map_download_errors(url, e)
        raise mapped from e


_TIKTOK_PHOTO_RE = re.compile(r"^https://(?:www\.)?tiktok\.com/@([\w.-]+)/photo/(\d+)")


# #UFB-0039
def is_tiktok_photo_url(url: str) -> bool:
    return bool(_TIKTOK_PHOTO_RE.match(url))


# #UFB-0039
@dataclass
class GalleryDownload:
    """A downloaded photo post: `image_paths` in display order, and the
    post's `audio_path` (None when the post has no audio track)."""

    audio_path: str | None
    image_paths: list[str]


# #UFB-0039
def _tiktok_item(ydl: yt_dlp.YoutubeDL, url: str) -> dict:
    """The TikTok post's raw item data, via yt-dlp's TikTok extractor.
    yt-dlp rejects `/photo/` URLs but parses `/video/` pages of the same
    post id, including `imagePost`. Relies on a private yt-dlp method,
    so this is the one place to fix if a yt-dlp upgrade breaks it."""
    match = _TIKTOK_PHOTO_RE.match(url)
    user, post_id = match.group(1), match.group(2)
    extractor = ydl.get_info_extractor("TikTok")
    data, _status = extractor._extract_web_data_and_status(
        f"https://www.tiktok.com/@{user}/video/{post_id}", post_id
    )
    return data or {}


# #UFB-0039
def _write_atomic_bytes(path: str, content: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.part"
    with open(tmp_path, "wb") as f:
        f.write(content)
    os.replace(tmp_path, path)


# #UFB-0016, #UFB-0039
def _cached_gallery(gallery_dir: str, audio_path: str) -> GalleryDownload | None:
    images = sorted(
        p
        for p in glob.glob(os.path.join(gallery_dir, "*.jpg"))
        if not p.endswith(_INCOMPLETE_SUFFIXES)
    )
    if not images:
        return None
    audio = audio_path if os.path.exists(audio_path) else None
    for path in images + ([audio] if audio else []):
        _touch_atime(path)
    return GalleryDownload(audio_path=audio, image_paths=images)


# #UFB-0016, #UFB-0039, #BUG-0014
async def tiktok_gallery_download(url: str) -> GalleryDownload:
    """Download a TikTok photo post's images and audio into the cache.
    Raises UnsupportedUrlError when the post has no images."""
    stem = url_to_filename_stem(url)
    async with _url_lock(stem):
        return await _tiktok_gallery_download_locked(url, stem)


# #UFB-0016, #UFB-0039, #BUG-0014
async def _tiktok_gallery_download_locked(url: str, stem: str) -> GalleryDownload:
    gallery_dir = os.path.join(settings.CACHE_DIR, "gallery", stem)
    audio_path = os.path.join(settings.CACHE_DIR, f"{stem}.mp3")

    cached = _cached_gallery(gallery_dir, audio_path)
    if cached:
        logger.info(f"Gallery already exists for URL: {url}, skipping download.")
        metrics.record_cache(hit=True)  # #UFB-0045
        return cached

    metrics.record_cache(hit=False)  # #UFB-0045

    try:
        with _youtube_dl({"quiet": True}) as ydl:
            item = _tiktok_item(ydl, url)
            images = (item.get("imagePost") or {}).get("images") or []
            if not images:
                raise UnsupportedUrlError(f"No images found for URL: {url}")

            image_paths = []
            for index, image in enumerate(images, start=1):
                image_url = image["imageURL"]["urlList"][0]
                path = os.path.join(gallery_dir, f"{index:02d}.jpg")
                _write_atomic_bytes(path, ydl.urlopen(image_url).read())
                image_paths.append(path)

            audio = None
            music_url = (item.get("music") or {}).get("playUrl")
            if music_url:
                try:
                    _write_atomic_bytes(audio_path, ydl.urlopen(music_url).read())
                    audio = audio_path
                except Exception as e:
                    logger.warning(f"Failed to download audio for {url}: {e}")

        logger.info(f"Gallery download successful for URL: {url}")
        metrics.record_downloader("yt-dlp")  # #UFB-0045
        return GalleryDownload(audio_path=audio, image_paths=image_paths)

    except UnsupportedUrlError:
        raise
    except Exception as e:
        mapped = _map_download_errors(url, e)
        raise mapped from e


# Stems longer than this many UTF-8 bytes are truncated + hashed (#BUG-0014);
# leaves headroom under 255 for ".f137.mp4.part", ".jpg.tmp" and similar.
_MAX_STEM_BYTES = 200
_STEM_HASH_CHARS = 16


# #UFB-0016, #BUG-0014
def url_to_filename_stem(url: str) -> str:
    """Cache filename stem (no extension) derived from the whole URL.
    Over-long stems are truncated and end in a sha256 suffix of the URL."""
    stem = "".join(c if c.isalnum() else "_" for c in url)
    if len(stem.encode()) <= _MAX_STEM_BYTES:
        return stem
    digest = hashlib.sha256(url.encode()).hexdigest()[:_STEM_HASH_CHARS]
    keep = _MAX_STEM_BYTES - _STEM_HASH_CHARS - 1
    head = stem.encode()[:keep].decode(errors="ignore")
    return f"{head}_{digest}"
