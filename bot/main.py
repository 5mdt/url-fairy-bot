# Constants and Environment Setup
import os
import requests
import traceback
import yt_dlp
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from dotenv import load_dotenv
from urllib.parse import urlparse, urlunparse, parse_qs

load_dotenv()
BASE_URL = os.getenv("BASE_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CACHE_DIR = "/cache"


# Function to follow redirects and retrieve the clean URL
def follow_redirects(url):
    response = requests.head(url, allow_redirects=True)
    return urlunparse(urlparse(response.url)._replace(query=""))


# Function to sanitize a filename for the cached video
def sanitize_subfolder_name(url):
    return "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in url)


# Function to create subfolder based on sanitized URL and return full path
def create_subfolder_and_path(sanitized_url):
    subfolder_name = sanitize_subfolder_name(sanitized_url)
    subfolder_path = os.path.join(CACHE_DIR, subfolder_name)

    # Create subfolder if it doesn't exist
    os.makedirs(subfolder_path, exist_ok=True)

    # Return the path for the video inside the subfolder
    return os.path.join(subfolder_path, f"{subfolder_name}.mp4")


# Function to check if video is within size limits
def is_within_size_limit(video_path):
    file_size = os.path.getsize(video_path)
    return file_size <= 20 * 1024 * 1024  # 20 MB


# Function to clean TikTok video URL
def clean_tiktok_url(url):
    parsed_url = urlparse(url)
    video_id = parse_qs(parsed_url.query).get("video_id")
    if video_id:
        sanitized_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?video_id={video_id[0]}"
        return sanitized_url
    return url


# Command Handlers and Message Handlers
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)


# Command handler for the /start command
async def start(message: types.Message):
    await message.reply(
        "Hello! I'm your friendly URLFairyBot. Send me a URL to clean and extract data!"
    )


# Handler for processing incoming messages
@dp.message_handler(content_types=[types.ContentType.TEXT])
async def process_message(message: types.Message):
    message_text = message.text.strip()

    # Split the message by spaces or any other delimiter you prefer
    urls = message_text.split()

    tasks = []
    error_messages = []  # List to store invalid URL format errors

    for url in urls:
        if not url.startswith(("http", "www")):
            error_messages.append(f"Invalid URL format: {url}")
            continue

        tasks.append(handle_url(url, message))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            error_messages.append(str(result))

    # Send accumulated error messages, if any
    if error_messages:
        await message.reply("\n".join(error_messages))


async def handle_url(url, message):
    sanitized_url = follow_redirects(url)
    video_path = create_subfolder_and_path(sanitized_url)

    if "tiktok" in sanitized_url:
        sanitized_url = clean_tiktok_url(sanitized_url)

        # Download the video if it doesn't exist
        if not os.path.exists(video_path):
            await yt_dlp_download(sanitized_url)

        # Check if the video file exists after download attempt
        if os.path.exists(video_path):
            if is_within_size_limit(video_path):
                with open(video_path, "rb") as video_file:
                    await message.reply_video(video_file, caption=sanitized_url)
            else:
                file_link = (
                    f"https://{BASE_URL}/{sanitize_subfolder_name(sanitized_url)}/"
                )
                await message.reply(
                    f"Sorry, the attachment file is too big.\n"
                    f"Original URL: {sanitized_url}\n"
                    f"Use this link to download the file:\n{file_link}"
                )
        else:
            await message.reply(
                f"Sorry, the video from URL {sanitized_url} could not be downloaded or is missing."
            )
    else:
        await message.reply(f"Invalid URL format: {url}")


# Video Download and Processing Functions
# Function to download a video using yt_dlp
async def yt_dlp_download(url):
    try:
        video_path = create_subfolder_and_path(url)
        ydl_opts = {"outtmpl": video_path}

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        error_message = (
            f"Error downloading video from URL: {url}. Error details: {str(e)}"
        )
        traceback.print_exc()
        return error_message


# Main function to start the bot
def main():
    # Create the cache directory if it doesn't exist
    os.makedirs(CACHE_DIR, exist_ok=True)

    # Start the bot using the Dispatcher
    executor.start_polling(dp, skip_updates=True)


if __name__ == "__main__":
    main()
