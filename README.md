# Telegram Renamer Bot

This bot monitors a source channel, renames media files (Video/Document/Audio) by cleaning up filenames and captions using smart regex pattern matching, and forwards them to a target channel without the "Forwarded" tag.

## Features
- Detects Movie/Series Title, Year, Resolution, Season/Episode.
- Auto-renames files to standard format: `Title Year Resolution S00E00`.
- Removes spam links, ads, and garbage characters.
- Works with Movies and Series (including ambiguous formats).
- Deletes the original file from Source Channel after successful forwarding.

## Setup

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configuration:**
   Rename `.env.sample` to `.env` and fill in your details:
   - `API_ID`, `API_HASH`: Get from [my.telegram.org](https://my.telegram.org).
   - `BOT_TOKEN`: Get from @BotFather.
   - `SOURCE_CHANNEL`: ID of the channel to monitor (e.g., -100xxxx).
   - `TARGET_CHANNEL`: ID of the destination channel.
   - `LOG_CHANNEL`: ID of the channel for logs/errors.

3. **Run:**
   ```bash
   python3 bot.py
   ```

## Parser Logic
The logic is located in `media_parser.py` and covers:
- Year extraction (anchor).
- Title extraction (everything before year or metadata).
- Resolution detection (1080p, 720p, etc.).
- Season/Episode detection (S01E01, 1x01, Episode 1, etc.).
