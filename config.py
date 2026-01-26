import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Channels can be ID (int) or Username (str)
# If using IDs, they must be integers (often negative for channels, e.g. -100123456)
def parse_channel(val):
    if not val:
        return None
    try:
        return int(val)
    except ValueError:
        return val

SOURCE_CHANNEL = parse_channel(os.getenv("SOURCE_CHANNEL"))
TARGET_CHANNEL = parse_channel(os.getenv("TARGET_CHANNEL"))
LOG_CHANNEL = parse_channel(os.getenv("LOG_CHANNEL")) # For error notifications

# Optional: Custom removal list
SPAM_KEYWORDS = [
    "MoviesFlix", "MoviesVerse", "YTS", "YIFY", 
    "www.", ".com", ".org", ".in", ".net", ".co",
    "TamilRockers", "Kuttymovies", "Hindi", "English",
    "Dual Audio", "ESub", "Sub", "x264", "x265", "HEVC",
    "WEBRip", "BluRay", "HDRip", "AAC", "10bit"
    # Note: Some of these (like "English") might be part of the title in rare cases, 
    # but usually are metadata. The parser will handle metadata separation intelligently.
]
