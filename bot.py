import os
import sys
import logging
import asyncio
from pyrogram import Client, filters, idle, utils
from pyrogram.errors import FloodWait
from aiohttp import web

# Monkeypatch Pyrogram to support 64-bit Channel IDs
utils.MIN_CHANNEL_ID = -1009999999999

from config import API_ID, API_HASH, BOT_TOKEN, SOURCE_CHANNEL, TARGET_CHANNEL, LOG_CHANNEL
from media_parser import parse_media_info
from web_server import start_web_server
from tmdb_client import TMDBClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment Variable Validation
if not API_ID:
    logger.error("API_ID is missing.")
    sys.exit(1)
if not API_HASH:
    logger.error("API_HASH is missing.")
    sys.exit(1)
if not BOT_TOKEN:
    logger.error("BOT_TOKEN is missing.")
    sys.exit(1)

# Set workers=1 to ensure sequential processing (FIFO) of messages
# This solves the issue of out-of-order forwarding for series batches.
app = Client("renamer_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=1)
tmdb = TMDBClient()

def get_file_name(message):
    if message.video:
        return message.video.file_name
    elif message.document:
        return message.document.file_name
    elif message.audio:
        return message.audio.file_name
    return None

def get_file_id(message):
    if message.video:
        return message.video.file_id
    elif message.document:
        return message.document.file_id
    elif message.audio:
        return message.audio.file_id
    return None

async def send_with_flood_handling(func, *args, **kwargs):
    try:
        return await func(*args, **kwargs)
    except FloodWait as e:
        logger.warning(f"FloodWait hit. Sleeping for {e.value} seconds.")
        await asyncio.sleep(e.value)
        return await send_with_flood_handling(func, *args, **kwargs)
    except Exception as e:
        logger.error(f"Error in send_with_flood_handling: {e}")
        raise e

# Updated Filter: Removed ~filters.edited as it doesn't exist in Pyrogram v2 on_message
@app.on_message(filters.chat(SOURCE_CHANNEL) & (filters.document | filters.video | filters.audio))
async def handle_media(client, message):
    try:
        file_name = get_file_name(message)
        caption = message.caption or ""
        
        # If no filename, try to use caption or default
        if not file_name:
            if caption:
                file_name = caption.split('\n')[0] # Use first line of caption
            else:
                file_name = "Unknown_File"

        logger.info(f"Processing: {file_name}")

        # Parse Media Info (Local Regex)
        info = parse_media_info(file_name, caption)
        
        # TMDB Enrichment
        if info.title and len(info.title) > 2:
            is_series = info.season is not None

            # Run blocking TMDB call in a thread executor to avoid blocking the event loop
            try:
                loop = asyncio.get_running_loop()
                tmdb_result = await loop.run_in_executor(None, tmdb.search_media, info.title, info.year, is_series)

                if tmdb_result:
                    logger.info(f"TMDB Found: {tmdb_result['title']} ({tmdb_result['year']})")
                    info.title = tmdb_result['title']
                    if tmdb_result['year']:
                        info.year = tmdb_result['year']
                else:
                    logger.info("TMDB search returned no results.")
            except Exception as e:
                logger.error(f"Error during TMDB lookup: {e}")

        # Validation: If title seems too short or empty, it might be a failure
        if not info.title or len(info.title) < 2:
            error_msg = f"Failed to parse title for: {file_name}\nCaption: {caption}"
            logger.warning(error_msg)
            if LOG_CHANNEL:
                await send_with_flood_handling(client.send_message, LOG_CHANNEL, error_msg)
            return

        new_caption = str(info)
        logger.info(f"New Caption: {new_caption}")
        
        # Send to Target Channel
        sent = None
        file_id = get_file_id(message)
        
        if message.video:
            sent = await send_with_flood_handling(
                client.send_video,
                chat_id=TARGET_CHANNEL,
                video=file_id,
                caption=new_caption,
                supports_streaming=True
            )
        elif message.document:
            sent = await send_with_flood_handling(
                client.send_document,
                chat_id=TARGET_CHANNEL,
                document=file_id,
                caption=new_caption,
                force_document=True
            )
        elif message.audio:
            sent = await send_with_flood_handling(
                client.send_audio,
                chat_id=TARGET_CHANNEL,
                audio=file_id,
                caption=new_caption
            )
            
        if sent:
            logger.info(f"Sent to target: {sent.id}")
            # Delete original message
            try:
                await send_with_flood_handling(message.delete)
                logger.info("Original message deleted.")
            except Exception as e:
                logger.error(f"Failed to delete original message: {e}")
        else:
            logger.error("Failed to send message.")

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        if LOG_CHANNEL:
            try:
                await send_with_flood_handling(client.send_message, LOG_CHANNEL, f"Error processing message: {str(e)}")
            except Exception as log_error:
                logger.error(f"Failed to send error to LOG_CHANNEL: {log_error}")

async def main():
    # Start Web Server
    logger.info("Starting Web Server...")
    web_app = await start_web_server()
    runner = web.AppRunner(web_app)
    await runner.setup()
    bind_address = "0.0.0.0"
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, bind_address, port)
    await site.start()
    logger.info(f"Web Server running on port {port}")

    # Start Bot
    logger.info("Starting Bot...")
    await app.start()
    logger.info("Bot started!")

    # Idle to keep the script running
    await idle()

    # Cleanup
    logger.info("Stopping Bot...")
    await app.stop()
    logger.info("Stopping Web Server...")
    await runner.cleanup()

if __name__ == "__main__":
    try:
        # Check for loop
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(main())
