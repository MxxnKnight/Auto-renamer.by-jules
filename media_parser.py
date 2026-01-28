import re
import os
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
    # Priority: Remove well-formed handles first (e.g., @Rocky_links)
    title = re.sub(r'@[a-zA-Z0-9_]+', '', title)

    # Then handle residual @ parts if any (like @mobile_mm.maryan where . connects)
    if title.strip().startswith('@'):
        parts = re.split(r'[ ._]+', title)
        if parts and parts[0].startswith('@'):
            parts.pop(0)
        while parts and len(parts) > 1 and len(parts[0]) <= 3:
            parts.pop(0)
        title = " ".join(parts)

    # 4. Remove content in square brackets [] globally
    title = re.sub(r'\[.*?\]', '', title)

    # 5. Handle "Prefix - Title" pattern
    if ' - ' in title:
        segments = title.split(' - ')
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
    # Regex Improvement:
    # 1. Greedy \d+ for episode to allow backtracking against the Lookahead

    # Priority 0: Merged Resolution (S01E01720p)
    # Matches S01E01 followed by 720p
    match = re.search(r'S(\d+)\s?E(\d+)(?=(\d{3,4}p))', text, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))

    # Priority 0.5: Merged Resolution Digits (S01E01720) - ambiguous but best effort
    # Matches S01E01 followed by 720 and end/boundary
    match = re.search(r'S(\d+)\s?E(\d+)(?=(\d{3,4}(?!\d)))', text, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))

    # Priority 1: S01E01 format (Standard)
    # Rejects S01E720p because 720 is followed by p
    match = re.search(r'S(\d{1,2})\s?E(\d{1,3})(?!\d|p)', text, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))
    
    # Priority 2: 1x01 format
    match = re.search(r'(\d{1,2})x(\d{1,3})(?!\d|p)', text, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))
    
    # Priority 3: Episode 1 / Ep 1
    match = re.search(r'(?:Episode|Ep)\s?\.?(\d{1,4})', text, re.IGNORECASE)
    if match:
        return None, int(match.group(1))
        
    # Priority 4: " - 123 " (Anime style)
    match = re.search(r'\s-\s(\d{1,4})(?:\s|\[|\.|$)', text)
    if match:
        return None, int(match.group(1))

    # Priority 5: Episode Number: 1
    match = re.search(r'Episode Number:\s?(\d+)', text, re.IGNORECASE)
    if match:
        return None, int(match.group(1))

    # Priority 6: 1/23 (fractions)
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

def parse_media_info(filename, caption=None, search_type=None):
    # Strip extension if present
    base_name, ext = os.path.splitext(filename)
    if ext.lower() in ['.mkv', '.mp4', '.avi', '.flv', '.mov', '.wmv', '.webm', '.mpg', '.mpeg', '.3gp']:
        raw_text = base_name
    else:
        raw_text = filename
    
    split_idx, found_year_str = find_metadata_split(raw_text)
    
    year = int(found_year_str) if found_year_str else None
    title_part = raw_text
    meta_part = "" # Fixed scope issue
    
    if split_idx != -1:
        title_part = raw_text[:split_idx]
        if found_year_str:
             meta_part = raw_text[split_idx+4:]
        else:
             meta_part = raw_text[split_idx:]
    
    # Combine caption and meta_part for extra detail extraction
    # Use rstrip() to avoid removing leading whitespace from meta_part (crucial for " - Ep" regex)
    full_meta_text = (meta_part + " " + (caption or "")).rstrip()

    resolution = extract_resolution(full_meta_text) or extract_resolution(raw_text) or "720p"
    season, episode = extract_season_episode(full_meta_text) or extract_season_episode(raw_text) or (None, None)
    
    # Clean Title
    clean_t = clean_title(title_part)
    # Only fallback to raw_text if we didn't find a split
    if not clean_t:
        if split_idx == -1:
            clean_t = clean_title(raw_text)
        elif split_idx == 0 and found_year_str:
            # Special case: The filename starts with a Year (e.g. "1917.mkv" or "2012.mkv")
            # In this case, the Year is likely the Title.
            clean_t = found_year_str

    # Fallback: If title is empty or too short, try to parse from Caption
    if (not clean_t or len(clean_t) < 2) and caption:
        cap_split_idx, cap_year_str = find_metadata_split(caption)

        if cap_split_idx != -1:
            cap_title_part = caption[:cap_split_idx]
        else:
            # If no metadata split found in caption, assume the whole caption is the title
            # This helps with cases like "One Piece 1015" where 1015 isn't caught by standard regex
            cap_title_part = caption

        clean_t_cap = clean_title(cap_title_part)
        if len(clean_t_cap) >= 2:
            clean_t = clean_t_cap
            # If we switched to caption for title, we might want to trust caption for Year too
            if cap_year_str:
                year = int(cap_year_str)

    # Aggressive Series Logic
    # If search_type is series, and we didn't find an episode via standard regex,
    # try to find a standalone number at the end of the title/text.
    if search_type == 'series' and episode is None:
        # Look for trailing number in the cleaned title
        # e.g. "One Piece 236" -> title="One Piece", ep=236

        # Regex for trailing number: spaces, then digits, then end of string
        match = re.search(r'\s(\d{1,4})$', clean_t)
        if match:
            found_ep = int(match.group(1))
            # Potential Title remainder
            potential_title = clean_t[:match.start()].strip()

            # Safety Check: Title shouldn't be empty or just symbols
            if len(potential_title) >= 2:
                episode = found_ep
                season = 1 # Default to S01
                clean_t = potential_title

    # Extract new fields
    source = extract_source(full_meta_text) or extract_source(raw_text)
    codec = extract_codec(full_meta_text) or extract_codec(raw_text)
    audio = extract_audio(full_meta_text) or extract_audio(raw_text)

    return MediaInfo(clean_t, year, resolution, season, episode, source, audio, codec)
