import os
import sys
import logging
import asyncio
import time
from pyrogram import Client, filters, idle, utils
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait
from aiohttp import web
from collections import deque

# Monkeypatch Pyrogram
utils.MIN_CHANNEL_ID = -1009999999999

from config import (
    API_ID, API_HASH, BOT_TOKEN, 
    SOURCE_MOVIES_CHANNEL, SOURCE_SERIES_CHANNEL, 
    TARGET_CHANNEL, LOG_CHANNEL, ADMIN_IDS,
    SPAM_KEYWORDS, save_spam_keyword, CAPTION_TEMPLATE
)
from media_parser import parse_media_info
from web_server import start_web_server
from tmdb_client import TMDBClient
from self_ping import ping_server

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Client("renamer_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=1)
tmdb = TMDBClient()

processed_messages = deque(maxlen=5000)
processed_files = set()
pending_messages = set()
user_states = {} 
stats = {"start_time": time.time(), "processed_count": 0, "errors": 0}
processing_queue = None

# --- UI Components ---

def get_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Spam", callback_data="menu_add_spam"),
         InlineKeyboardButton("➖ Delete Spam", callback_data="menu_del_spam")],
        [InlineKeyboardButton("📋 Current Spams", callback_data="menu_all_spam")],
        [InlineKeyboardButton("⚙️ Template", callback_data="menu_template")]
    ])

def get_back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_home")]])

# --- Logic ---

async def worker():
    while True:
        try:
            client, message, search_type = await processing_queue.get()
            try:
                await process_media_request(client, message, search_type)
                await asyncio.sleep(3)
            finally:
                processing_queue.task_done()
        except Exception as e:
            logger.error(f"Worker Error: {e}")
            await asyncio.sleep(5)

async def process_media_request(client, message, search_type):
    unique_id = f"{message.chat.id}:{message.id}"
    
    file_name = None
    file_uid = None
    if message.video: file_name, file_uid = message.video.file_name, message.video.file_id
    elif message.document: file_name, file_uid = message.document.file_name, message.document.file_id
    elif message.audio: file_name, file_uid = message.audio.file_name, message.audio.file_id

    if not file_uid or unique_id in processed_messages or file_uid in processed_files:
        if unique_id in pending_messages: pending_messages.remove(unique_id)
        return

    processed_messages.append(unique_id)
    processed_files.add(file_uid)
    if unique_id in pending_messages: pending_messages.remove(unique_id)

    try:
        caption = message.caption or ""
        info = parse_media_info(file_name or caption, caption, search_type=search_type)
        
        # Precision TMDB Lookup
        if info.title and len(info.title) > 2:
            tmdb_res = await tmdb.search_media(info.title, info.year, is_series=(search_type == 'series'))
            if tmdb_res:
                info.title = tmdb_res['title']
                info.year = tmdb_res['year'] # Prioritize TMDB truth

        new_caption = str(info)
        
        if message.video:
            sent = await client.send_video(TARGET_CHANNEL, video=file_uid, caption=new_caption, supports_streaming=True)
        elif message.document:
            sent = await client.send_document(TARGET_CHANNEL, document=file_uid, caption=new_caption, force_document=True)
        elif message.audio:
            sent = await client.send_audio(TARGET_CHANNEL, audio=file_uid, caption=new_caption)

        if sent:
            stats["processed_count"] += 1
            try: await message.delete()
            except: pass
        else: stats["errors"] += 1

    except Exception as e:
        logger.error(f"Processing Error: {e}")
        stats["errors"] += 1

# --- Handlers ---

@app.on_message(filters.command("start") & filters.user(ADMIN_IDS))
async def start_cmd(client, message):
    user_states.pop(message.from_user.id, None)
    await message.reply_text(
        "🛠️ **Auto-Renamer Precision Control**\n\nManage your blocklist and settings below.",
        reply_markup=get_main_menu()
    )

@app.on_callback_query(filters.user(ADMIN_IDS))
async def handle_callbacks(client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id
    
    if data == "menu_home":
        user_states.pop(user_id, None)
        await query.message.edit_text("🛠️ **Auto-Renamer Precision Control**", reply_markup=get_main_menu())
    
    elif data == "menu_add_spam":
        user_states[user_id] = "waiting_for_spam_add"
        await query.message.edit_text("📝 **Add Keyword**\n\nSend the word to block.", reply_markup=get_back_button())
    
    elif data == "menu_del_spam":
        user_states[user_id] = "waiting_for_spam_del"
        await query.message.edit_text("🗑️ **Delete Keyword**\n\nSend the word to remove.", reply_markup=get_back_button())
    
    elif data == "menu_all_spam":
        words = ", ".join(f"`{k}`" for k in SPAM_KEYWORDS[:60])
        await query.message.edit_text(f"📋 **Blocklist**\n\n{words}", reply_markup=get_back_button())
    
    elif data == "menu_template":
        await query.message.edit_text(f"⚙️ **Active Template**\n\n`{CAPTION_TEMPLATE}`", reply_markup=get_back_button())

@app.on_message(filters.user(ADMIN_IDS) & filters.text & ~filters.regex(r"^/"))
async def handle_admin_inputs(client, message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    if not state: return

    from config import SPAM_KEYWORDS, save_spam_keyword
    word = message.text.strip()
    
    if state == "waiting_for_spam_add":
        if word not in SPAM_KEYWORDS:
            SPAM_KEYWORDS.append(word)
            SPAM_KEYWORDS.sort(key=len, reverse=True)
            save_spam_keyword(word)
            await message.reply_text(f"✅ Added `{word}`", reply_markup=get_back_button())
        else: await message.reply_text("❌ Already in list.")
    
    elif state == "waiting_for_spam_del":
        if word in SPAM_KEYWORDS:
            SPAM_KEYWORDS.remove(word)
            save_spam_keyword(word, remove=True)
            await message.reply_text(f"✅ Removed `{word}`", reply_markup=get_back_button())
        else: await message.reply_text("❌ Not found.")
    
    user_states.pop(user_id, None)

@app.on_message((filters.chat(SOURCE_MOVIES_CHANNEL) | filters.chat(SOURCE_SERIES_CHANNEL)) & (filters.document | filters.video | filters.audio))
async def on_media(client, message):
    if message.chat.id == TARGET_CHANNEL or (message.from_user and message.from_user.is_bot): return
    unique_id = f"{message.chat.id}:{message.id}"
    if unique_id in pending_messages or unique_id in processed_messages: return
    search_type = 'series' if message.chat.id == SOURCE_SERIES_CHANNEL else 'movie'
    pending_messages.add(unique_id)
    await processing_queue.put((client, message, search_type))

async def main():
    global processing_queue
    processing_queue = asyncio.Queue()
    web_app = await start_web_server()
    runner = web.AppRunner(web_app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8080))).start()
    ping_url = os.getenv("PING_URL") or os.getenv("RENDER_EXTERNAL_URL")
    if ping_url: asyncio.create_task(ping_server(ping_url))
    await app.start()
    
    # Notify Admins & Log Channel on Startup
    startup_msg = "🚀 **Auto-Renamer is now Live and Precision-Ready!**"
    for admin_id in ADMIN_IDS:
        try: await app.send_message(admin_id, startup_msg)
        except: pass
    if LOG_CHANNEL:
        try: await app.send_message(LOG_CHANNEL, startup_msg)
        except: pass

    asyncio.create_task(worker())
    logger.info("Bot started.")
    await idle()
    await app.stop()
    await runner.cleanup()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
