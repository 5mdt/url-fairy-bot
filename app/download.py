# download.py

import os
import logging
import yt_dlp
from app.config import settings

logger = logging.getLogger(__name__)

async def yt_dlp_download(url: str) -> str:
    video_path = os.path.join(settings.CACHE_DIR, f"{sanitize_subfolder_name(url)}.mp4")
    if os.path.exists(video_path):
        return video_path

    try:
        ydl_opts = {"outtmpl": video_path}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return video_path
    except Exception as e:
        logger.error(f"Download failed for URL: {url}, error: {e}")
        return None

def sanitize_subfolder_name(url: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in url)
