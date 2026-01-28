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

# Message ID Cache for Deduplication
# Stores the last 1000 processed message IDs
processed_messages = deque(maxlen=1000)

# Pending Messages Set (for fast O(1) lookups before queueing)
pending_messages = set()

# Global Processing Queue for Strict Sequential Processing
# Initialized in main() to ensure loop binding
processing_queue = None

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

async def worker():
    logger.info("Worker started. Waiting for tasks...")
    while True:
        try:
            # Get task from queue
            client, message, search_type = await processing_queue.get()

            try:
                logger.info(f"Worker picked up message: {message.id} ({search_type})")

                # Process the request
                await process_media_request(client, message, search_type)

                # Rate limiting / Delay between files
                # User requested "no need to rush, you can allow rate limit time delay"
                logger.info("Worker sleeping for 3 seconds...")
                await asyncio.sleep(3)
            finally:
                processing_queue.task_done()

        except Exception as e:
            logger.error(f"Worker crashed: {e}", exc_info=True)
            # Prevent worker from dying completely, just restart loop
            await asyncio.sleep(5)

async def process_media_request(client, message, search_type):
    unique_id = (message.chat.id, message.id)

    # Remove from pending, add to processed
    if unique_id in pending_messages:
        pending_messages.remove(unique_id)

    # Redundant check in case pending logic was bypassed or race condition
    if unique_id in processed_messages:
        logger.warning(f"Message {unique_id} already processed. Skipping.")
        return

    # Add to cache immediately
    processed_messages.append(unique_id)

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
            logger.info(f"Sent to target: {sent.id} (Channel ID: {TARGET_CHANNEL})")

            # Double check we didn't send to source
            if sent.chat.id == message.chat.id:
                 logger.critical("CRITICAL: Bot sent file back to Source Channel! Infinite Loop Risk!")

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

# Register Handlers conditionally
if SOURCE_MOVIES_CHANNEL:
    @app.on_message(filters.chat(SOURCE_MOVIES_CHANNEL) & (filters.document | filters.video | filters.audio))
    async def handle_movies(client, message):
        # Ignore own messages
        if message.from_user and message.from_user.is_self:
            return

        unique_id = (message.chat.id, message.id)
        if unique_id in pending_messages or unique_id in processed_messages:
            logger.info(f"Ignoring duplicate/pending message: {message.id}")
            return

        if processing_queue:
            logger.info(f"Queued Movie Request: {message.id}")
            pending_messages.add(unique_id)
            await processing_queue.put((client, message, 'movie'))
        else:
            logger.error("Processing Queue not initialized!")
else:
    logger.warning("SOURCE_MOVIES_CHANNEL not set. Movie monitoring disabled.")

if SOURCE_SERIES_CHANNEL:
    @app.on_message(filters.chat(SOURCE_SERIES_CHANNEL) & (filters.document | filters.video | filters.audio))
    async def handle_series(client, message):
        # Ignore own messages
        if message.from_user and message.from_user.is_self:
            return

        unique_id = (message.chat.id, message.id)
        if unique_id in pending_messages or unique_id in processed_messages:
            logger.info(f"Ignoring duplicate/pending message: {message.id}")
            return

        if processing_queue:
            logger.info(f"Queued Series Request: {message.id}")
            pending_messages.add(unique_id)
            await processing_queue.put((client, message, 'series'))
        else:
            logger.error("Processing Queue not initialized!")
else:
    logger.warning("SOURCE_SERIES_CHANNEL not set. Series monitoring disabled.")

async def main():
    global processing_queue
    # Initialize Queue with the running event loop
    processing_queue = asyncio.Queue()

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
    await app.start()
    logger.info("Bot started!")

    # Start Worker Task
    asyncio.create_task(worker())

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
