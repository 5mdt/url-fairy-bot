# -*- coding: utf-8 -*-
import asyncio
import logging
import os
import traceback
from urllib.parse import parse_qs, urlparse, urlunparse

import requests
import yt_dlp
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize constants from environment variables
BASE_URL = os.getenv("BASE_URL", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CACHE_DIR = os.getenv("CACHE_DIR", "/cache/")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Configure logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))

# Define logger
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Check if required environment variables are set
if not all([BASE_URL, BOT_TOKEN]):
    raise ValueError("BASE_URL or BOT_TOKEN environment variables are not set")


async def follow_redirects(url, timeout=10):
    """
    Follow redirects for a given URL and retrieve the final URL after redirection.

    Args:
        url (str): The initial URL to follow redirects for.
        timeout (int): Timeout for the HTTP request.

    Returns:
        str: The final URL after following redirects or the original URL if it times out.
    """
    logger.debug("✨ Start following URL: %s", url)

    # Dictionary to store domain name replacements
    domain_replacements = {
        "https://twitter.com/": "https://www.fxtwitter.com/",
        "https://www.instagram.com/p/": "https://www.ddinstagram.com/p/",
        "https://www.instagram.com/reel/": "https://www.ddinstagram.com/reel/",
        "https://www.twitter.com/": "https://www.fxtwitter.com/",
        "https://x.com/": "https://www.fxtwitter.com/",
        # Add more mappings as needed
    }

    # Check if the URL starts with any of the keys in the domain_replacements dictionary
    for domain, replacement in domain_replacements.items():
        if url.startswith(domain):
            logger.debug("✨ Replacable link found: %s", url)
            # Replace the domain name with the corresponding replacement
            return url.replace(domain, replacement)

    # If the URL does not match any of the mappings, follow redirects using requests
    try:
        response = requests.head(url, allow_redirects=True, timeout=timeout)
        return urlunparse(urlparse(response.url)._replace(query=""))
    except requests.exceptions.Timeout:
        logger.warning("✨ Timeout occurred while following redirects for URL: %s", url)
        return url


def sanitize_subfolder_name(url):
    """
    Sanitize the URL to create a valid subfolder name.

    Args:
        url (str): The URL to sanitize.

    Returns:
        str: The sanitized subfolder name.
    """
    logger.debug("✨ Sanitize subfolder name for URL: %s", url)
    return "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in url)


def create_subfolder_and_path(sanitized_url):
    """
    Create a subfolder based on the sanitized URL and return the full path for video storage.

    Args:
        sanitized_url (str): The sanitized URL.

    Returns:
        str: The full path to store the video inside the subfolder.
    """
    logger.info("✨ Create a subfolder for URL: %s", sanitized_url)

    subfolder_name = sanitize_subfolder_name(sanitized_url)
    subfolder_path = os.path.join(CACHE_DIR, subfolder_name)
    os.makedirs(subfolder_path, exist_ok=True)
    return os.path.join(subfolder_path, f"{subfolder_name}.mp4")


def clean_tiktok_url(url):
    """
    Clean the TikTok video URL by extracting the video_id.

    Args:
        url (str): The TikTok URL to clean.

    Returns:
        str: The cleaned TikTok URL.
    """
    logger.debug("✨ Clean the TikTok video URL: %s", url)

    parsed_url = urlparse(url)
    video_id = parse_qs(parsed_url.query).get("video_id")
    if video_id:
        sanitized_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?video_id={video_id[0]}"
        return sanitized_url
    return url


def transform_tiktok_url(url):
    """Transform TikTok URL to the embed format for yt-dlp."""
    logger.debug("✨ Transform TikTok URL to the embed format: %s", url)

    parsed_url = urlparse(url)
    video_path = parsed_url.path.strip("/")
    video_id = video_path.split("/")[-1]
    transformed_url = f"https://www.tiktok.com/embed/v2/{video_id}"
    return transformed_url


async def start(message: types.Message):
    """Command handler for the /start command."""
    logger.info("✨ Start command received: /start")

    await message.reply(
        "Hello! I'm your friendly URLFairyBot. Send me a URL to clean and extract data!"
    )


@dp.message_handler(content_types=[types.ContentType.TEXT])
async def process_message(message: types.Message):
    """Handler for processing incoming messages."""
    logger.debug("✨ Message received: %s", message.text)

    error_messages = []
    if message.chat.type != types.ChatType.PRIVATE:
        if not any(word.startswith(("http", "www")) for word in message.text.split()):
            error_messages.append(f"Invalid URL format: {message.text}")
            return

    message_text = message.text.strip()
    urls = message_text.split()
    tasks = []

    # Check if there are valid URLs in the message
    valid_urls_exist = any(url.startswith(("http", "www")) for url in urls)

    for url in urls:
        if not url.startswith(("http", "www")):
            logger.debug("✨ Invalid URL format: %s", url)
            error_messages.append(f"Invalid URL format: {url}")
            continue
        tasks.append(handle_url(url, message))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            error_messages.append(str(result))
    if (
        error_messages and not valid_urls_exist
    ):  # Only send error messages if valid URLs exist
        await message.reply("\n".join(error_messages))


async def handle_url(url, message):
    """Handle individual URLs to process and send media."""
    logger.debug("✨ Handle individual URL: %s", url)
    original_sanitized_url = await follow_redirects(url)

    if (
        original_sanitized_url.startswith("https://www.fxtwitter.com")
        or original_sanitized_url.startswith("https://fxtwitter.com/")
        or original_sanitized_url.startswith("https://www.ddinstagram.com/p/")
        or original_sanitized_url.startswith("https://www.ddinstagram.com/reel/")
    ):
        # Check if the original sanitized URL matches any URL in the user's message
        if original_sanitized_url in url:
            return  # If matched, do not send any response

        await message.reply(
            f"Here is the link Telegram parses better: "
            f"[📎]({original_sanitized_url})",
            parse_mode=types.ParseMode.MARKDOWN,
        )
        return

    if "tiktok" in original_sanitized_url:
        logger.debug("✨ Tiktok link found: %s", original_sanitized_url)
        sanitized_url = transform_tiktok_url(original_sanitized_url)
    elif original_sanitized_url.startswith("https://www.youtube.com/shorts"):
        logger.debug("✨ YouTube shorts link found: %s", original_sanitized_url)
        sanitized_url = original_sanitized_url
    else:
        logger.debug("✨ Unsupported URL: %s", original_sanitized_url)
        # Only send this message in private chats
        if message.chat.type == types.ChatType.PRIVATE:
            await message.reply(
                f"Sorry, the media from URL {original_sanitized_url} is not supported."
            )
        return

    video_path = create_subfolder_and_path(sanitized_url)

    if not os.path.exists(video_path):
        logger.debug("✨ File has not been downloaded yet. Let's download.")
        await yt_dlp_download(sanitized_url)

    if os.path.exists(video_path):
        logger.debug("✨ Files exist, let's share the link")

        mp4_file_link = f"https://{BASE_URL}/{sanitize_subfolder_name(sanitized_url)}/{sanitize_subfolder_name(sanitized_url)}.mp4"
        await message.reply(
            f"[⏬ Download\n⏯️ Watch]({mp4_file_link})\n\n"
            f"[📎 Original]({original_sanitized_url})\n",
            parse_mode=types.ParseMode.MARKDOWN,
        )
    else:
        if message.chat.type == types.ChatType.PRIVATE:
            await message.reply(
                f"Sorry, the media from URL {original_sanitized_url} could not be downloaded or is missing."
            )


async def yt_dlp_download(url):
    """Download a video using yt_dlp with retries."""
    logger.info("✨ Download a video using yt_dlp: %s", {url})
    for attempt in range(3):
        try:
            video_path = create_subfolder_and_path(url)
            ydl_opts = {"outtmpl": video_path}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Save the original URL to a file if download was successful
            with open(
                os.path.join(
                    CACHE_DIR, sanitize_subfolder_name(url), "original_url.txt"
                ),
                "w",
            ) as f:
                f.write(url)
            logger.info("✨ Download was successful")
            return None  # Indicate successful download, exit loop
        except Exception as e:
            error_message = (
                f"Error downloading video from URL: {url}. Error details: {str(e)}"
            )
            traceback.logger.info_exc()
            logger.critical(error_message)
            # Wait 5 seconds before retrying
            await asyncio.sleep(5)

    # All retries failed, return error message
    return f"Failed to download video from URL: {url} after 3 attempts."


def main():
    """Main function to start the bot."""
    logger.info("✨Start polling")
    os.makedirs(CACHE_DIR, exist_ok=True)
    executor.start_polling(dp, skip_updates=False)


if __name__ == "__main__":
    logger.info("✨Url-fairy-bot initialized")
    main()
