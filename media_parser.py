import re
import os
from config import SPAM_KEYWORDS, CAPTION_TEMPLATE

class MediaInfo:
    def __init__(self, title, year=None, resolution="720p", season=None, episode=None,
                 source=None, audio=None, codec=None, is_series=False):
        self.title = title.strip()
        self.year = year
        self.resolution = resolution or "720p"
        self.season = season
        self.episode = episode
        self.source = source
        self.audio = audio
        self.codec = codec
        self.is_series = is_series

    def __str__(self):
        # Format: Title (Year) [Audio Resolution Source Codec Subtitle]
        # Or if series: Title Year Resolution S01E01
        
        # 1. Base Title and Year
        title_dots = self.title.replace(" ", ".")
        main_part = f"{title_dots}"
        if self.year:
            main_part += f".{self.year}"
        
        # 2. Resolution
        res = self.resolution
        if res.isdigit(): res = f"{res}p"
        
        # 3. Series Info
        series_info = ""
        if self.is_series:
            if self.season is not None and self.episode is not None:
                series_info = f"S{int(self.season):02d}E{int(self.episode):02d}"
            elif self.episode is not None:
                series_info = f"S01E{int(self.episode):02d}"

        # 4. Tags (Audio, Source, Codec) - Using dots for consistency
        tags = []
        if self.audio: tags.append(self.audio.replace(" ", "."))
        tags.append(res)
        if self.source: tags.append(self.source.replace(" ", "."))
        if self.codec: tags.append(self.codec.replace(" ", "."))
        
        tag_str = ".".join(tags)
        
        # Combine everything with dots
        result = [main_part, tag_str]
        if series_info: result.append(series_info)
        
        return ".".join(result)

def clean_title(title):
    # Aggressive URL/Handle removal
    title = re.sub(r'https?://\S+', '', title)
    title = re.sub(r'www\.[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}', '', title)
    title = re.sub(r'\b\S+\.(com|org|net|in|co|me|info|io|biz|site|xyz|top|cloud|online)\b', '', title, flags=re.IGNORECASE)
    title = title.replace("_", " ").replace(".", " ")
    title = re.sub(r'@[a-zA-Z0-9_]+', '', title)
    title = re.sub(r't\.me/\S+', '', title)
    title = re.sub(r'#\w+', '', title)
    title = re.sub(r'\[.*?\]', '', title)
    title = re.sub(r'\(.*?\)', '', title)
    
    if ' - ' in title:
        segments = title.split(' - ')
        if len(segments[0]) < 15 or any(k.lower() in segments[0].lower() for k in ["Join", "Update", "Channel"]):
            title = segments[-1]

    title = re.sub(r'[^a-zA-Z0-9\s]', ' ', title)
    for keyword in sorted(SPAM_KEYWORDS, key=len, reverse=True):
        pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
        title = pattern.sub(' ', title)

    title = re.sub(r'\s+', ' ', title).strip()
    return title

def extract_resolution(text):
    res_pattern = r'\b(\d{3,4}p|4k|8k)\b'
    match = re.search(res_pattern, text, re.IGNORECASE)
    if match: return match.group(1).lower()
    return None

def extract_source(text):
    sources = [r'WEB[-_\s]?DL', r'WEB[-_\s]?Rip', r'BluRay', r'HDTV', r'DVD[-_\s]?Rip', r'BRRip', r'HDRip']
    for p in sources:
        m = re.search(p, text, re.IGNORECASE)
        if m: return m.group(0).upper().replace(" ", "-")
    return None

def extract_codec(text):
    codecs = [r'[hx]\.?26[45]', r'HEVC', r'10bit']
    found = []
    for p in codecs:
        m = re.search(p, text, re.IGNORECASE)
        if m: found.append(m.group(0).upper())
    return " ".join(found) if found else None

def extract_audio(text):
    audios = [r'Hindi', r'English', r'Tamil', r'Telugu', r'Malayalam', r'Kannada', r'Dual[-_\s]?Audio', r'Multi[-_\s]?Audio', r'DDP\s?\d\.\d', r'AAC']
    found = []
    for p in audios:
        m = re.search(p, text, re.IGNORECASE)
        if m: found.append(m.group(0).title())
    return " ".join(found) if found else None

def extract_season_episode(text):
    match = re.search(r'S(\d{1,2})\s?E(\d{1,3})(?!\d|p)', text, re.IGNORECASE)
    if match: return int(match.group(1)), int(match.group(2))
    match = re.search(r'(?:Episode|Ep)\s?\.?(\d{1,4})', text, re.IGNORECASE)
    if match: return None, int(match.group(1))
    return None, None

def parse_media_info(filename, caption=None, search_type=None):
    base_name, _ = os.path.splitext(filename)
    raw_text = filename
    combined_text = (caption or "") + " " + filename
    
    # Extract Year
    year = None
    year_match = re.search(r'(?<!\d)(19|20)\d{2}(?!\d)', combined_text)
    if year_match: year = int(year_match.group(0))

    # Extract Resolution
    resolution = extract_resolution(combined_text) or "720p"
    
    # Extract Title (everything before metadata)
    title_part = base_name
    meta_split = re.search(r'((19|20)\d{2}|S\d+E\d+|\d{3,4}p)', base_name, re.IGNORECASE)
    if meta_split:
        title_part = base_name[:meta_split.start()]
    
    clean_t = clean_title(title_part)
    if len(clean_t) < 2 and caption:
        clean_t = clean_title(caption.split('\n')[0])

    # Rich Extraction
    source = extract_source(combined_text)
    codec = extract_codec(combined_text)
    audio = extract_audio(combined_text)
    season, episode = extract_season_episode(combined_text)

    is_series = (search_type == 'series')
    
    return MediaInfo(clean_t, year, resolution, season, episode, source, audio, codec, is_series)
