# url_processing.py

import re
import logging
import os
import requests
from urllib.parse import urlparse, urlunparse

from app.config import settings
from .download import yt_dlp_download, UnsupportedUrlError

logger = logging.getLogger(__name__)

# Define the function to follow redirects
def follow_redirects(url: str, timeout=10) -> str:
    try:
        response = requests.head(url, allow_redirects=True, timeout=timeout)
        redirected_url = urlunparse(urlparse(response.url)._replace(query=""))

        if not urlparse(redirected_url).scheme or not urlparse(redirected_url).netloc:
            logger.warning(f"Invalid redirect URL: {redirected_url}")
            return url  # Return original URL if redirect is invalid

        return redirected_url
    except requests.Timeout:
        logger.warning(f"Timeout for URL: {url}")
        return url

# Updated rewrite_map to handle specific domain changes only
rewrite_map = {
    r"^https://(www\.)?tiktok\.com": "https://tfxktok.com",
    r"^https://(www\.)?twitter\.com": "https://www.fxtwitter.com",
    r"^https://(www\.)?x\.com": "https://www.fxtwitter.com",
    r"^https://(www\.)?instagram\.com/p/": "https://www.ddinstagram.com/p/",
    r"^https://(www\.)?instagram\.com/reel/": "https://www.ddinstagram.com/reel/",
}

async def process_url_request(url: str, is_group_chat: bool = False) -> str:
    try:
        final_url = follow_redirects(url)
        video_os_path = await yt_dlp_download(final_url)

        if video_os_path:
            video_path = os.path.join(*video_os_path.split(os.path.sep)[-1:])
            response = (
                "[Click here to ⏯️ Watch or ⏬ Download]"
                + f"(https://{settings.BASE_URL}/{video_path})"
                + f"\n\n[📎 Original]({final_url})"
            )
            return response
        else:
            logger.error("Video download failed unexpectedly.")

    except UnsupportedUrlError:
        # Apply URL rewrite if final_url matches any regex pattern in rewrite_map
        modified_url = final_url
        for pattern, replacement in rewrite_map.items():
            if re.match(pattern, final_url):
                # Replace only the matching domain part with the replacement
                modified_url = re.sub(pattern, replacement, final_url, count=1)
                break

        response = (
            "I failed to download the file by myself."
            + "\n\nHere is an alternative link, which Telegram may parse better: "
            + f"\n[📎 Modified URL]({modified_url})"
            + f"\n\n[📎 Original]({final_url})\n"
        )
        return response

    except requests.exceptions.RequestException as req_e:
        logger.error(f"Request error processing URL: {req_e}")
        return None
    except Exception as e:
        logger.error(f"Error processing URL: {e}")
        return None
