import re
from config import SPAM_KEYWORDS

class MediaInfo:
    def __init__(self, title, year=None, resolution="720p", season=None, episode=None,
                 source=None, audio=None, codec=None):
        self.title = title.strip()
        self.year = year
        self.resolution = resolution
        self.season = season
        self.episode = episode
        self.source = source
        self.audio = audio
        self.codec = codec

    def __str__(self):
        # Format: Title Year Resolution S00E00 [Source] [Audio] [Codec]
        parts = [self.title]
        if self.year:
            parts.append(str(self.year))
        
        parts.append(self.resolution)
        
        if self.season is not None and self.episode is not None:
            parts.append(f"S{int(self.season):02d}E{int(self.episode):02d}")
        elif self.episode is not None:
            parts.append(f"S01E{int(self.episode):02d}")

        # Add enriched info
        if self.source:
            parts.append(self.source)
        if self.codec:
            parts.append(self.codec)
        if self.audio:
            parts.append(self.audio)
            
        return " ".join(parts)

def clean_title(title):
    # 1. Remove URLs
    title = re.sub(r'https?://\S+', '', title)

    # 2. Remove Hashtags (words starting with #)
    title = re.sub(r'#\w+', '', title)

    # 3. Handle Telegram Handles
    if title.startswith('@'):
        parts = re.split(r'[ ._]+', title)
        if parts and parts[0].startswith('@'):
            parts.pop(0)
        while parts and len(parts) > 1 and len(parts[0]) <= 3:
            parts.pop(0)
        title = " ".join(parts)
    else:
        title = re.sub(r'@[a-zA-Z0-9_]+', '', title)

    # 4. Remove content in square brackets [] globally
    title = re.sub(r'\[.*?\]', '', title)

    # 5. Handle "Prefix - Title" pattern
    # If the title contains " - ", usually the part after the last hyphen is the real title
    # Exception: "Mission - Impossible" (Keep "Mission - Impossible")?
    # This is tricky. But for "ReleaseGroup - Title", stripping the prefix is desired.
    # Heuristic: If we find " - ", let's look at the segments.
    # If there are 2 segments, and the first one is short (< 10 chars) or looks like garbage, drop it.
    if ' - ' in title:
        segments = title.split(' - ')
        # If last segment is decent length, use it.
        # Check against "Mission - Impossible" -> "Impossible" (bad).
        # Check "RF_RF - Sirai" -> "Sirai" (good).
        # Let's try: take the last segment if it's not empty.
        # To be safer, maybe only if previous segment looks "spammy" or "prefix-y"?
        # But user explicitly wants "RF_RF - Sirai" -> "Sirai".
        # Let's take the last segment for now as it's the most common "clean" pattern in piracy/forwarding.
        if segments:
            title = segments[-1]

    # 6. Remove dots, underscores
    title = title.replace(".", " ").replace("_", " ")
    
    # Remove custom spam keywords
    for keyword in sorted(SPAM_KEYWORDS, key=len, reverse=True):
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        title = pattern.sub(' ', title)

    # Remove starting non-alphanumeric chars
    title = re.sub(r'^[^a-zA-Z0-9]+', '', title)
    
    # Remove trailing non-alphanumeric chars
    title = re.sub(r'[^a-zA-Z0-9]+$', '', title)
    
    # Remove extra spaces
    title = re.sub(r'\s+', ' ', title).strip()
    return title

def extract_resolution(text):
    res_pattern = r'(\d{3,4}p|4k|8k)'
    match = re.search(res_pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return None

def extract_season_episode(text):
    match = re.search(r'S(\d+)\s?E(\d+)', text, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))
    
    match = re.search(r'(\d+)x(\d+)', text, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))
    
    match = re.search(r'(?:Episode|Ep)\s?\.?(\d+)', text, re.IGNORECASE)
    if match:
        return None, int(match.group(1))
        
    match = re.search(r'\s-\s(\d+)(?:\s|\[|\.|$)', text)
    if match:
        return None, int(match.group(1))

    match = re.search(r'Episode Number:\s?(\d+)', text, re.IGNORECASE)
    if match:
        return None, int(match.group(1))

    match = re.search(r'(\d+)/(\d+)', text)
    if match and "episode" in text.lower():
         return None, int(match.group(1))

    return None, None

def extract_source(text):
    # WEB-DL, WEBRip, BluRay, HDTV, DVDRip, BD-Rip, BRRip
    sources = [
        r'WEB[-_\s]?DL', r'WEB[-_\s]?Rip', r'BluRay', r'HDTV',
        r'DVD[-_\s]?Rip', r'BD[-_\s]?Rip', r'BRRip', r'HDRip'
    ]
    for pattern in sources:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Normalize common ones
            found = match.group(0).upper()
            if "WEB" in found:
                if "DL" in found: return "WEB-DL"
                if "RIP" in found: return "WEBRip"
            return found
    return None

def extract_codec(text):
    # H.264, H.265, HEVC, x264, x265, 10bit
    # 10bit is often associated with codec
    codecs = [
        r'[hx]\.?26[45]', r'HEVC', r'AVC', r'10bit'
    ]
    found_codecs = []
    for pattern in codecs:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = match.group(0)
            # Normalize
            if "265" in val or "HEVC" in val.upper():
                val = "HEVC"
            elif "264" in val:
                val = "x264"
            found_codecs.append(val)
    
    # De-duplicate and join (e.g. HEVC 10bit)
    return " ".join(sorted(list(set(found_codecs)))) if found_codecs else None

def extract_audio(text):
    # Hindi, English, Tamil, Telugu, Dual Audio, Multi Audio, DDP5.1, DDP2.0, AAC, AC3
    audios = [
        r'Hindi', r'English', r'Tamil', r'Telugu', r'Malayalam', r'Kannada',
        r'Dual[-_\s]?Audio', r'Multi[-_\s]?Audio',
        r'DDP\s?\d\.\d', r'DD\s?\d\.\d', r'AAC', r'AC3', r'E?Sub'
    ]
    found_audio = []
    for pattern in audios:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for m in matches:
            val = m.group(0)
            # Capitalize nicely
            if "audio" in val.lower():
                val = val.title()
            elif "ddp" in val.lower():
                val = val.upper()
            elif val.lower() in ["hindi", "english", "tamil", "telugu"]:
                val = val.title()

            if val not in found_audio:
                found_audio.append(val)

    return " ".join(found_audio) if found_audio else None

def find_metadata_split(text):
    year_match = re.search(r'(?<!\d)(19|20)\d{2}(?!\d)', text)
    if year_match:
        return year_match.start(), year_match.group(0)
        
    se_patterns = [
        r'S(\d+)\s?E(\d+)',
        r'(\d+)x(\d+)',
        r'(?:Episode|Ep)\s?\.?(\d+)',
        r'\s-\s(\d+)(?:\s|\[|\.|$)'
    ]
    for pat in se_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            return match.start(), None
            
    res_match = re.search(r'(\d{3,4}p|4k|8k)', text, re.IGNORECASE)
    if res_match:
        return res_match.start(), None
        
    return -1, None

def parse_media_info(filename, caption=None):
    raw_text = filename
    
    split_idx, found_year_str = find_metadata_split(raw_text)
    
    year = int(found_year_str) if found_year_str else None
    title_part = raw_text
    meta_part = ""
    
    if split_idx != -1:
        title_part = raw_text[:split_idx]
        if found_year_str:
             meta_part = raw_text[split_idx+4:]
        else:
             meta_part = raw_text[split_idx:]
    
    # Combine caption and meta_part for extra detail extraction
    full_meta_text = (meta_part + " " + (caption or "")).strip()

    resolution = extract_resolution(full_meta_text) or extract_resolution(raw_text) or "720p"
    season, episode = extract_season_episode(full_meta_text) or extract_season_episode(raw_text) or (None, None)
    
    # Extract new fields
    source = extract_source(full_meta_text) or extract_source(raw_text)
    codec = extract_codec(full_meta_text) or extract_codec(raw_text)
    audio = extract_audio(full_meta_text) or extract_audio(raw_text)

    # Clean Title
    clean_t = clean_title(title_part)
    if not clean_t:
        clean_t = clean_title(raw_text)

    # Remove details from title if they leaked in (rare but possible)
    # (Simplified for now as clean_title removes most junk)

    return MediaInfo(clean_t, year, resolution, season, episode, source, audio, codec)
