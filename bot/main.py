import os
import requests
import traceback
import yt_dlp
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from dotenv import load_dotenv
from urllib.parse import urlparse, urlunparse, parse_qs

# Load environment variables from .env file
load_dotenv()
BASE_URL = os.getenv("BASE_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CACHE_DIR = "/video_cache"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)


# Command handler for the /start command
async def start(message: types.Message):
    await message.reply(
        "Hello! I'm your friendly URLFairyBot. Send me a URL to clean and extract data!"
    )


# Function to follow redirects and retrieve the clean URL
def follow_redirects(url):
    response = requests.head(url, allow_redirects=True)
    return urlunparse(urlparse(response.url)._replace(query=""))


# Function to sanitize a filename for the cached video
def sanitize_filename(filename):
    return "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in filename)


# Function to download a video using yt_dlp
async def yt_dlp_download(url):
    try:
        ydl_opts = {"outtmpl": os.path.join(CACHE_DIR, sanitize_filename(url) + ".mp4")}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        error_message = (
            f"Error downloading video from URL: {url}. Error details: {str(e)}"
        )
        traceback.print_exc()
        return error_message


# Function to handle sending large video
async def send_large_video(message, clean_url, file_link):
    await message.reply(
        f"Sorry, the attachment file is too big.\nOriginal URL: {clean_url}\nUse this link to download the file:\n{file_link}"
    )


# Function to check if video is within size limits
def is_within_size_limit(video_path):
    file_size = os.path.getsize(video_path)
    return file_size <= 20 * 1024 * 1024  # 20 MB


# Handler for processing incoming messages
@dp.message_handler(content_types=[types.ContentType.TEXT])
async def process_message(message: types.Message):
    message_text = message.text.strip()

    # Split the message by spaces or any other delimiter you prefer
    urls = message_text.split()

    error_messages = []  # List to store invalid URL format errors

    for url in urls:
        if url.startswith(("http", "www")):
            clean_url = follow_redirects(url)
            video_path = os.path.join(CACHE_DIR, sanitize_filename(clean_url) + ".mp4")
            file_link = f"https://{BASE_URL}/{sanitize_filename(clean_url)}.mp4"

            if "tiktok" in clean_url:
                clean_url = clean_tiktok_url(clean_url)
                if os.path.exists(video_path):
                    try:
                        if is_within_size_limit(video_path):
                            with open(video_path, "rb") as video_file:
                                await message.reply_video(video_file, caption=clean_url)
                        else:
                            await send_large_video(message, clean_url, file_link)
                    except Exception as e:
                        error_message = f"Error sending video from URL: {clean_url}. Error details: {str(e)}"
                        traceback.print_exc()
                        await message.reply(error_message)
                else:
                    await yt_dlp_download_and_send(clean_url, message)
            else:
                error_messages.append(
                    f"Invalid URL format: {url}"
                )  # Accumulate the error messages
        else:
            error_messages.append(
                f"Invalid URL format: {url}"
            )  # Accumulate the error messages

    # Check if there are any accumulated error messages and send them as one reply
    if error_messages:
        await message.reply("\n".join(error_messages))


# Function to download a video using yt_dlp and send it
async def yt_dlp_download_and_send(clean_url, message):
    try:
        video_path = os.path.join(CACHE_DIR, sanitize_filename(clean_url) + ".mp4")
        await yt_dlp_download(clean_url)

        if is_within_size_limit(video_path):
            with open(video_path, "rb") as video_file:
                await message.reply_video(video_file, caption=clean_url)
        else:
            file_link = f"https://{BASE_URL}/{sanitize_filename(clean_url)}.mp4"
            await send_large_video(message, clean_url, file_link)
    except Exception as e:
        error_message = f"Error processing video from URL: {clean_url}"
        traceback.print_exc()
        await message.reply(error_message)


# Function to clean TikTok video URL
def clean_tiktok_url(url):
    parsed_url = urlparse(url)
    video_id = parse_qs(parsed_url.query).get("video_id")
    if video_id:
        clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?video_id={video_id[0]}"
        return clean_url
    return url


# Main function to start the bot
def main():
    # Create the cache directory if it doesn't exist
    os.makedirs(CACHE_DIR, exist_ok=True)

    # Start the bot using the Dispatcher
    executor.start_polling(dp, skip_updates=True)


if __name__ == "__main__":
    main()
