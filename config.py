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

SOURCE_MOVIES_CHANNEL = parse_channel(os.getenv("SOURCE_MOVIES_CHANNEL"))
SOURCE_SERIES_CHANNEL = parse_channel(os.getenv("SOURCE_SERIES_CHANNEL"))
TARGET_CHANNEL = parse_channel(os.getenv("TARGET_CHANNEL"))
LOG_CHANNEL = parse_channel(os.getenv("LOG_CHANNEL")) # For error notifications

# Admin IDs (list of integers)
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

# Strict Formatting Template
# Dot separated: Title.Year.Resolution.S01E01
CAPTION_TEMPLATE = "{title}.{year}.{resolution}.{episode_info}"

# Expanded Spam Keywords and Promotion Patterns
DEFAULT_SPAM = [
    # Websites & Handles
    "MoviesFlix", "MoviesVerse", "YTS", "YIFY", "PSA", "GalaxyRG",
    "www.", ".com", ".org", ".in", ".net", ".co", "t.me", "telegram.me",
    "TamilRockers", "Kuttymovies", "Movierulz", "1337x", "PirateBay",
    
    # Common Promotion Text
    "Join", "Our", "Sub", "Subscribe", "Follow", "Update", "Channel", "Group",
    "Link", "Direct", "Download", "Watch", "Online", "Free",
    
    # Metadata
    "Hindi", "English", "Tamil", "Telugu", "Malayalam", "Kannada", "Dual Audio", "Multi Audio",
    "x264", "x265", "HEVC", "10bit", "8bit", "AAC", "DDP5.1", "DDP2.0", "AC3",
    "WEBRip", "BluRay", "HDRip", "WEB-DL", "DVDRip", "BRRip", "BDRip"
]

CUSTOM_SPAM_FILE = "custom_spam.txt"

def load_spam_keywords():
    keywords = set(DEFAULT_SPAM)
    if os.path.exists(CUSTOM_SPAM_FILE):
        with open(CUSTOM_SPAM_FILE, "r", encoding="utf-8") as f:
            for line in f:
                word = line.strip()
                if word: keywords.add(word)
    return list(keywords)

def save_spam_keyword(word, remove=False):
    keywords = set()
    if os.path.exists(CUSTOM_SPAM_FILE):
        with open(CUSTOM_SPAM_FILE, "r", encoding="utf-8") as f:
            keywords = {line.strip() for line in f if line.strip()}
    
    if remove:
        keywords.discard(word)
    else:
        keywords.add(word)
    
    with open(CUSTOM_SPAM_FILE, "w", encoding="utf-8") as f:
        for kw in sorted(list(keywords)):
            f.write(f"{kw}\n")

SPAM_KEYWORDS = load_spam_keywords()
