import os
import sys
import logging
import asyncio
from pyrogram import Client, filters, idle, utils
from pyrogram.errors import FloodWait
from aiohttp import web
from collections import deque
import time

# Monkeypatch Pyrogram to support 64-bit Channel IDs
utils.MIN_CHANNEL_ID = -1009999999999

from config import API_ID, API_HASH, BOT_TOKEN, SOURCE_MOVIES_CHANNEL, SOURCE_SERIES_CHANNEL, TARGET_CHANNEL, LOG_CHANNEL, ADMIN_IDS
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

# Set workers=1 to ensure sequential processing
app = Client("renamer_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=1)
tmdb = TMDBClient()

# In-memory stats and cache
processed_messages = deque(maxlen=5000)
processed_files = set()
pending_messages = set()
stats = {
    "start_time": time.time(),
    "processed_count": 0,
    "errors": 0
}

processing_queue = None

def get_file_name(message):
    if message.video: return message.video.file_name
    if message.document: return message.document.file_name
    if message.audio: return message.audio.file_name
    return None

def get_file_id(message):
    if message.video: return message.video.file_id
    if message.document: return message.document.file_id
    if message.audio: return message.audio.file_id
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
    logger.info("Worker started.")
    while True:
        try:
            client, message, search_type = await processing_queue.get()
            try:
                await process_media_request(client, message, search_type)
                await asyncio.sleep(3) # Respect rate limits
            finally:
                processing_queue.task_done()
        except Exception as e:
            logger.error(f"Worker Error: {e}", exc_info=True)
            await asyncio.sleep(5)

async def process_media_request(client, message, search_type):
    unique_id = f"{message.chat.id}:{message.id}"
    file_uid = get_file_id(message)

    if unique_id in processed_messages or file_uid in processed_files:
        if unique_id in pending_messages: pending_messages.remove(unique_id)
        return

    processed_messages.append(unique_id)
    processed_files.add(file_uid)
    if unique_id in pending_messages: pending_messages.remove(unique_id)

    try:
        file_name = get_file_name(message)
        caption = message.caption or ""
        
        info = parse_media_info(file_name or caption, caption, search_type=search_type)
        
        # TMDB Lookup (Async)
        if info.title and len(info.title) > 2:
            tmdb_res = await tmdb.search_media(info.title, info.year, is_series=(search_type == 'series'))
            if tmdb_res:
                info.title = tmdb_res['title']
                if tmdb_res['year']:
                    info.year = tmdb_res['year']

        new_name = str(info)
        logger.info(f"Renaming: {file_name} -> {new_name}")

        sent = None
        if message.video:
            sent = await send_with_flood_handling(client.send_video, TARGET_CHANNEL, video=file_uid, caption=new_name, supports_streaming=True)
        elif message.document:
            sent = await send_with_flood_handling(client.send_document, TARGET_CHANNEL, document=file_uid, caption=new_name, force_document=True)
        elif message.audio:
            sent = await send_with_flood_handling(client.send_audio, TARGET_CHANNEL, audio=file_uid, caption=new_name)

        if sent:
            stats["processed_count"] += 1
            try:
                await message.delete()
            except: pass
        else:
            stats["errors"] += 1

    except Exception as e:
        logger.error(f"Processing Error: {e}")
        stats["errors"] += 1
        if LOG_CHANNEL:
            await send_with_flood_handling(client.send_message, LOG_CHANNEL, f"Error: {str(e)}\nFile: {file_name}")

# Admin Handlers
@app.on_message(filters.command("status") & filters.user(ADMIN_IDS))
async def status_cmd(client, message):
    uptime = time.time() - stats["start_time"]
    msg = (f"**Bot Status**\n\n"
           f"Uptime: `{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m`\n"
           f"Processed: `{stats['processed_count']}`\n"
           f"Errors: `{stats['errors']}`\n"
           f"Queue: `{processing_queue.qsize()}`\n"
           f"Pending: `{len(pending_messages)}`")
    await message.reply_text(msg)

@app.on_message(filters.command("broadcast") & filters.user(ADMIN_IDS) & filters.reply)
async def broadcast_cmd(client, message):
    try:
        await message.reply_to_message.copy(TARGET_CHANNEL)
        await message.reply_text("Broadcast sent to Target Channel.")
    except Exception as e:
        await message.reply_text(f"Broadcast failed: {e}")

# Media Handlers
@app.on_message((filters.chat(SOURCE_MOVIES_CHANNEL) | filters.chat(SOURCE_SERIES_CHANNEL)) & (filters.document | filters.video | filters.audio))
async def on_media(client, message):
    if message.chat.id == TARGET_CHANNEL: return
    if message.from_user and message.from_user.is_bot: return

    unique_id = f"{message.chat.id}:{message.id}"
    if unique_id in pending_messages or unique_id in processed_messages: return

    search_type = 'series' if message.chat.id == SOURCE_SERIES_CHANNEL else 'movie'
    pending_messages.add(unique_id)
    await processing_queue.put((client, message, search_type))

async def main():
    global processing_queue
    processing_queue = asyncio.Queue()

    # Web Server & Self-Ping
    web_app = await start_web_server()
    runner = web.AppRunner(web_app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8080))).start()

    ping_url = os.getenv("PING_URL") or os.getenv("RENDER_EXTERNAL_URL")
    if ping_url: asyncio.create_task(ping_server(ping_url))

    await app.start()
    asyncio.create_task(worker())
    logger.info("Bot is running...")
    await idle()
    await app.stop()
    await runner.cleanup()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
