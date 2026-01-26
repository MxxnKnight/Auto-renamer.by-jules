import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from config import API_ID, API_HASH, BOT_TOKEN, SOURCE_CHANNEL, TARGET_CHANNEL, LOG_CHANNEL
from media_parser import parse_media_info

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Client("renamer_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

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

        # Parse Media Info
        info = parse_media_info(file_name, caption)
        
        # Validation: If title seems too short or empty, it might be a failure
        if not info.title or len(info.title) < 2:
            error_msg = f"Failed to parse title for: {file_name}\nCaption: {caption}"
            logger.warning(error_msg)
            if LOG_CHANNEL:
                await client.send_message(LOG_CHANNEL, error_msg)
            return

        new_caption = str(info)
        logger.info(f"New Caption: {new_caption}")
        
        # Send to Target Channel
        # Using send_video/document with file_id prevents re-uploading and removes forward tag
        sent = None
        file_id = get_file_id(message)
        
        if message.video:
            sent = await client.send_video(
                chat_id=TARGET_CHANNEL,
                video=file_id,
                caption=new_caption,
                supports_streaming=True
            )
        elif message.document:
            sent = await client.send_document(
                chat_id=TARGET_CHANNEL,
                document=file_id,
                caption=new_caption,
                force_document=True
            )
        elif message.audio:
            sent = await client.send_audio(
                chat_id=TARGET_CHANNEL,
                audio=file_id,
                caption=new_caption
            )
            
        if sent:
            logger.info(f"Sent to target: {sent.id}")
            # Delete original message
            try:
                await message.delete()
                logger.info("Original message deleted.")
            except Exception as e:
                logger.error(f"Failed to delete original message: {e}")
        else:
            logger.error("Failed to send message.")

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        if LOG_CHANNEL:
            await client.send_message(LOG_CHANNEL, f"Error processing message: {str(e)}")

if __name__ == "__main__":
    logger.info("Bot started...")
    app.run()
