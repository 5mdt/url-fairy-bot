# -*- coding: utf-8 -*-
import asyncio
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
BASE_URL = os.getenv("BASE_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CACHE_DIR = "/cache"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Check if environment variables are set
if BASE_URL is None or BOT_TOKEN is None:
    raise ValueError("BASE_URL or BOT_TOKEN environment variables are not set")


async def follow_redirects(url):
    """
    Follow redirects for a given URL and retrieve the final URL after redirection.

    Args:
        url (str): The initial URL to follow redirects for.

    Returns:
        str: The final URL after following redirects.
    """
    print("✨ Start following URL: " + url)

    # Dictionary to store domain name replacements
    domain_replacements = {
        "https://www.twitter.com/": "https://www.fxtwitter.com/",
        "https://twitter.com/": "https://www.fxtwitter.com/",
        "https://x.com/": "https://www.fxtwitter.com/",
        "https://www.instagram.com/reel": "https://www.ddinstagram.com/reel",
        # Add more mappings as needed
    }

    # Check if the URL starts with any of the keys in the domain_replacements dictionary
    for domain, replacement in domain_replacements.items():
        if url.startswith(domain):
            print("✨ Replacable link found")
            # Replace the domain name with the corresponding replacement
            return url.replace(domain, replacement)

    # If the URL does not match any of the mappings, follow redirects using requests
    response = requests.head(url, allow_redirects=True)
    return urlunparse(urlparse(response.url)._replace(query=""))


def sanitize_subfolder_name(url):
    """
    Sanitize the URL to create a valid subfolder name.

    Args:
        url (str): The URL to sanitize.

    Returns:
        str: The sanitized subfolder name.
    """
    print("✨ Sanitize subfolder name for URL: " + url)
    return "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in url)


def create_subfolder_and_path(sanitized_url):
    """
    Create a subfolder based on the sanitized URL and return the full path for video storage.

    Args:
        sanitized_url (str): The sanitized URL.

    Returns:
        str: The full path to store the video inside the subfolder.
    """
    print("✨ Create a subfolder for URL: " + sanitized_url)

    subfolder_name = sanitize_subfolder_name(sanitized_url)
    subfolder_path = os.path.join(CACHE_DIR, subfolder_name)
    os.makedirs(subfolder_path, exist_ok=True)
    return os.path.join(subfolder_path, f"{subfolder_name}.mp4")


def is_within_size_limit(video_path):
    """
    Check if the video file size is within the allowed limit (10 MB).

    Args:
        video_path (str): The path to the video file.

    Returns:
        bool: True if the video file size is within the limit, otherwise False.
    """
    print("✨ Check if video size is within limit for path: " + video_path)

    file_size = os.path.getsize(video_path)
    return file_size <= 10 * 1024 * 1024


def clean_tiktok_url(url):
    """
    Clean the TikTok video URL by extracting the video_id.

    Args:
        url (str): The TikTok URL to clean.

    Returns:
        str: The cleaned TikTok URL.
    """
    print("✨ Clean the TikTok video URL: " + url)

    parsed_url = urlparse(url)
    video_id = parse_qs(parsed_url.query).get("video_id")
    if video_id:
        sanitized_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?video_id={video_id[0]}"
        return sanitized_url
    return url


def transform_tiktok_url(url):
    """Transform TikTok URL to the embed format for yt-dlp."""
    print("✨ Transform TikTok URL to the embed format: " + url)

    parsed_url = urlparse(url)
    video_path = parsed_url.path.strip("/")
    video_id = video_path.split("/")[-1]
    transformed_url = f"https://www.tiktok.com/embed/v2/{video_id}"
    return transformed_url


async def start(message: types.Message):
    """Command handler for the /start command."""
    print("✨ Start command received: /start")

    await message.reply(
        "Hello! I'm your friendly URLFairyBot. Send me a URL to clean and extract data!"
    )


@dp.message_handler(content_types=[types.ContentType.TEXT])
async def process_message(message: types.Message):
    """Handler for processing incoming messages."""
    print(f"✨ Message received: {message.text}")

    if message.chat.type != types.ChatType.PRIVATE:
        if not any(word.startswith(("http", "www")) for word in message.text.split()):
            error_messages.append(f"Invalid URL format: {url}")
            return

    message_text = message.text.strip()
    urls = message_text.split()
    tasks = []
    error_messages = []

    # Check if there are valid URLs in the message
    valid_urls_exist = any(url.startswith(("http", "www")) for url in urls)

    for url in urls:
        if not url.startswith(("http", "www")):
            print(f"✨ Invalid URL format: {url}")
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
    print("✨ Handle individual URL: " + url)
    original_sanitized_url = await follow_redirects(url)

    if (
        original_sanitized_url.startswith("https://www.fxtwitter.com")
        or original_sanitized_url.startswith("https://fxtwitter.com/")
        or original_sanitized_url.startswith("https://www.ddinstagram.com/reel")
    ):
        await message.reply(f"{original_sanitized_url}")
        return

    if "tiktok" in original_sanitized_url:
        sanitized_url = transform_tiktok_url(original_sanitized_url)
    else:
        sanitized_url = original_sanitized_url

    if "tiktok" in sanitized_url:
        print("✨ Tiktok link found")
        video_path = create_subfolder_and_path(sanitized_url)
        sanitized_url = clean_tiktok_url(sanitized_url)

        if not os.path.exists(video_path):
            print("✨ This file was not downloaded yet. Lets download")
            await yt_dlp_download(sanitized_url)

        if os.path.exists(video_path):
            print("✨ Files exist, lets share them")

            media_files_to_send = [
                os.path.join(os.path.dirname(video_path), filename)
                for filename in os.listdir(os.path.dirname(video_path))
                if is_within_size_limit(
                    os.path.join(os.path.dirname(video_path), filename)
                )
            ]

            if media_files_to_send:
                for i in range(0, len(media_files_to_send), 10):
                    batch_media_files = media_files_to_send[i : i + 10]
                    media_group = [
                        (
                            types.InputMediaVideo(
                                media=open(file_path, "rb"),
                                caption=original_sanitized_url,
                            )
                            if file_path.endswith(".mp4")
                            else types.InputMediaPhoto(
                                media=open(file_path, "rb"),
                                caption=original_sanitized_url,
                            )
                        )
                        for file_path in batch_media_files
                    ]
                    await bot.send_media_group(message.chat.id, media_group)
            else:
                file_link = (
                    f"https://{BASE_URL}/{sanitize_subfolder_name(sanitized_url)}/"
                )
                await message.reply(
                    f"Sorry, all media in the attachment folder are too big.\n"
                    f"Use this link to download or watch the media:\n{file_link}\n"
                    f"Original URL: {original_sanitized_url}\n"
                )
        else:
            await message.reply(
                f"Sorry, the media from URL {original_sanitized_url} could not be downloaded or is missing."
            )
    return


async def yt_dlp_download(url):
    """Download a video using yt_dlp."""
    print(f"✨ Download a video using yt_dlp: {url}")
    try:
        video_path = create_subfolder_and_path(url)
        ydl_opts = {"outtmpl": video_path}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Save the original URL to a file if download was successful
        print(os.path.join(video_path, "original_url.txt"))
        with open(os.path.join(CACHE_DIR, sanitize_subfolder_name(url), "original_url.txt"), "w") as f:
            f.write(url)

    except Exception as e:
        error_message = (
            f"Error downloading video from URL: {url}. Error details: {str(e)}"
        )
        traceback.print_exc()
        print(error_message)
        return error_message


def main():
    """Main function to start the bot."""
    print("✨Start polling")
    os.makedirs(CACHE_DIR, exist_ok=True)
    executor.start_polling(dp, skip_updates=False)


if __name__ == "__main__":
    print("✨Url-fairy-bot initialized")
    main()
