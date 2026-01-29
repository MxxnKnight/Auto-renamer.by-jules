import os
import sys
import logging
import asyncio
from pyrogram import Client, filters, idle, utils
from pyrogram.errors import FloodWait
from aiohttp import web
from collections import deque

# Monkeypatch Pyrogram to support 64-bit Channel IDs
utils.MIN_CHANNEL_ID = -1009999999999

from config import API_ID, API_HASH, BOT_TOKEN, SOURCE_MOVIES_CHANNEL, SOURCE_SERIES_CHANNEL, TARGET_CHANNEL, LOG_CHANNEL
from media_parser import parse_media_info
from web_server import start_web_server
from tmdb_client import TMDBClient
from self_ping import ping_server

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

# GLOBAL DEDUPLICATION CACHES
seen_message_ids = set()
seen_movie_files = set()
seen_series_episodes = set()

# STEP 1: ADD THIS HELPER (GLOBAL)
def trace(message):
    unique_id = (
        message.video.file_unique_id if message.video else
        message.document.file_unique_id if message.document else
        message.audio.file_unique_id if message.audio else
        None
    )
    return f"chat={message.chat.id} msg={message.id} unique_id={unique_id}"

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

def get_unique_id(message):
    if message.video:
        return message.video.file_unique_id
    elif message.document:
        return message.document.file_unique_id
    elif message.audio:
        return message.audio.file_unique_id
    return None

def get_file_size(message):
    if message.video:
        return message.video.file_size
    elif message.document:
        return message.document.file_size
    elif message.audio:
        return message.audio.file_size
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

async def process_media_request(client, message, search_type):
    try:
        file_name = get_file_name(message)
        caption = message.caption or ""
        
        # If no filename, try to use caption or default
        if not file_name:
            if caption:
                file_name = caption.split('\n')[0] # Use first line of caption
            else:
                file_name = "Unknown_File"

        logger.info(f"Received File ({search_type}): {file_name}")

        # Parse Media Info (Local Regex) with search_type hint
        # search_type argument ensures 'movie' files get Season/Episode stripped
        info = parse_media_info(file_name, caption, search_type=search_type)

        # FIX: One Piece Anime Year Force
        if info.title and info.title.lower() == "one piece" and not info.year:
            info.year = 1999

        # SPLIT DEDUPLICATION LOGIC
        if search_type == 'movie':
            # STEP 2: MOVIES — FILE SIZE DEDUPE ONLY
            file_size = get_file_size(message)
            if file_size:
                movie_key = f"{file_size}"
                if movie_key in seen_movie_files:
                    logger.warning(f"[MOVIE-SKIP] Telegram duplicate movie detected | {trace(message)}")
                    return
                seen_movie_files.add(movie_key)

                # Memory Safety
                if len(seen_movie_files) > 5000:
                    seen_movie_files.clear()

        elif search_type == 'series':
            # STEP 3: SERIES — EPISODE NUMBER ONLY
            season = info.season or 1
            episode = info.episode if info.episode is not None else 0 # Safe default

            series_key = f"s{season:02d}e{episode:02d}"

            if series_key in seen_series_episodes:
                logger.warning(f"[SERIES-SKIP] Duplicate episode detected ({series_key}) | {trace(message)}")
                return

            seen_series_episodes.add(series_key)

            # Memory Safety
            if len(seen_series_episodes) > 5000:
                seen_series_episodes.clear()

        logger.info(f"Regex Parsed Title: '{info.title}' Year: {info.year} S: {info.season} E: {info.episode}")
        
        # TMDB Enrichment
        if info.title and len(str(info.title)) > 2:
            is_series_search = (search_type == 'series')

            # Run blocking TMDB call in a thread executor to avoid blocking the event loop
            try:
                loop = asyncio.get_running_loop()
                tmdb_result = await loop.run_in_executor(None, tmdb.search_media, info.title, info.year, is_series_search)

                if tmdb_result:
                    # Ensure title is a string to prevent 'builtin_function_or_method' len error
                    info.title = str(tmdb_result['title'])
                    if tmdb_result['year']:
                        info.year = tmdb_result['year']
                    # Use overview if needed, but not adding to caption currently
            except Exception as e:
                logger.error(f"Error during TMDB lookup: {e}")

        # Validation: If title seems too short or empty, it might be a failure
        # Force string conversion to prevent len() error on non-string types
        final_title = str(info.title) if info.title else ""
        if len(final_title) < 2:
            error_msg = f"Failed to parse title for: {file_name}\nCaption: {caption}"
            logger.warning(error_msg)
            if LOG_CHANNEL:
                await send_with_flood_handling(client.send_message, LOG_CHANNEL, error_msg)
            return

        new_caption = str(info)
        logger.info(f"Final Caption: {new_caption}")
        
        # Send to Target Channel
        sent = None
        file_id = get_file_id(message)
        
        # STEP 5: ADD SEND LOGS (BEFORE)
        logger.info(f"[SEND-START] Sending to target | {trace(message)}")

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
            # STEP 5: ADD SEND LOGS (AFTER)
            logger.info(f"[SEND-DONE] Sent to target | {trace(message)}")
            logger.info(f"Sent to target: {sent.id} (Channel ID: {TARGET_CHANNEL})")

            # Double check we didn't send to source
            if sent.chat.id == message.chat.id:
                 logger.critical("CRITICAL: Bot sent file back to Source Channel! Infinite Loop Risk!")

            # Delete original message
            try:
                # STEP 6: ADD DELETE LOGS (BEFORE)
                logger.info(f"[DELETE-START] Deleting source | {trace(message)}")
                await asyncio.sleep(0.5)
                await send_with_flood_handling(message.delete)
                # STEP 6: ADD DELETE LOGS (AFTER)
                logger.info(f"[DELETE-DONE] Deleted source | {trace(message)}")
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

# Register Handlers conditionally
if SOURCE_MOVIES_CHANNEL:
    @app.on_message(filters.chat(SOURCE_MOVIES_CHANNEL) & (filters.document | filters.video | filters.audio))
    async def handle_movies(client, message):
        # STEP 1: MESSAGE-LEVEL DEDUPE (MANDATORY)
        if message.id in seen_message_ids:
            return
        seen_message_ids.add(message.id)

        # HARD BLOCK TARGET CHANNEL
        if message.chat.id == TARGET_CHANNEL:
            return

        # ENSURE ONLY ONE HANDLER CAN PROCESS
        if message.chat.id != SOURCE_MOVIES_CHANNEL:
            return

        # Fix: Properly ignore bot’s own messages
        if message.from_user and message.from_user.is_bot:
            return
        if message.sender_chat and message.sender_chat.id == TARGET_CHANNEL:
            return

        logger.info(f"Directly processing Movie Request: {message.id}")
        await process_media_request(client, message, 'movie')

else:
    logger.warning("SOURCE_MOVIES_CHANNEL not set. Movie monitoring disabled.")

if SOURCE_SERIES_CHANNEL:
    # STEP 7: (OPTIONAL) BLOCK EDITED MESSAGES
    @app.on_message(
        filters.chat(SOURCE_SERIES_CHANNEL)
        & (filters.document | filters.video | filters.audio)
    )
    async def handle_series(client, message):
        # STEP 1: MESSAGE-LEVEL DEDUPE (MANDATORY)
        if message.id in seen_message_ids:
            return
        seen_message_ids.add(message.id)

        # STEP 3: ADD ENTRY LOG (SERIES HANDLER)
        logger.warning(f"[ENTRY] Series handler triggered | {trace(message)}")

        # HARD BLOCK TARGET CHANNEL
        if message.chat.id == TARGET_CHANNEL:
            return

        # ENSURE ONLY ONE HANDLER CAN PROCESS
        if message.chat.id != SOURCE_SERIES_CHANNEL:
            return

        # Fix: Properly ignore bot’s own messages
        if message.from_user and message.from_user.is_bot:
            return
        if message.sender_chat and message.sender_chat.id == TARGET_CHANNEL:
            return

        logger.info(f"Directly processing Series Request: {message.id}")
        await process_media_request(client, message, 'series')

else:
    logger.warning("SOURCE_SERIES_CHANNEL not set. Series monitoring disabled.")

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

    # Start Self-Ping (if URL is available)
    # Render sets RENDER_EXTERNAL_URL automatically for web services
    ping_url = os.getenv("PING_URL") or os.getenv("RENDER_EXTERNAL_URL")
    if ping_url:
        # Append / if not present (optional, standardizing)
        asyncio.create_task(ping_server(ping_url))
    else:
        logger.warning("No PING_URL or RENDER_EXTERNAL_URL found. Self-ping disabled.")

    # Start Bot
    logger.info("Starting Bot...")
    # STEP 2: ADD STARTUP LOG
    logger.critical("BOT STARTED — WATCHING FOR DUPLICATES")
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
