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
        segments = [s.strip() for s in title.split(' - ') if s.strip()]
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
    # 1) Explicit formats (highest priority)
    # S01E12, S1E12, E12, EP12, Episode 12
    # Fix: Added \b or non-word boundary check for 'e'/'ep' to avoid matching 'Stage 2' -> 'ge 2'
    match = re.search(r'(?i)(?:s(\d{1,2})\s*e(\d{1,3})|\b(?:e|ep|episode)\.?\s*(\d{1,4}))', text)
    if match:
        if match.group(1) and match.group(2):
            return int(match.group(1)), int(match.group(2))
        elif match.group(3):
            return None, int(match.group(3))

    # 1b) 1x01 format (Standard enough to keep in high priority)
    match = re.search(r'(\d{1,2})x(\d{1,3})(?!\d|p)', text, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))

    # 2) Underscore / dash isolated numbers (anime style)
    # _232_, - 206 -, .1122.
    match = re.search(r'(?<!\d)[._-](\d{1,4})[._-](?!\d)', text)
    if match:
        return None, int(match.group(1))
    
    # 2.1) Space-isolated leading-zero number (e.g. "Naruto 029 Title")
    # Must have leading zero to avoid matching years like "2002"
    match = re.search(r'(?<!\d)\s(0\d{1,3})(?=\s)', text)
    if match:
        return None, int(match.group(1))

    # 2.5) Trailing number after hyphen (One Piece - 1122)
    # Allows end of string or non-digit
    match = re.search(r'(?<!\d)\s-\s(\d{1,4})(?:$|[^\d])', text)
    if match:
        return None, int(match.group(1))

    # 3) Trailing number near resolution (VERY common)
    # One Piece 1122 720p, Naruto-206 [720p]
    match = re.search(r'(?<!\d)(\d{1,4})(?=\s*(?:\[)?(?:480p|720p|1080p|2160p|web|bluray))', text, re.IGNORECASE)
    if match:
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

    season, episode = extract_season_episode(full_meta_text)
    if season is None and episode is None:
        season, episode = extract_season_episode(raw_text)
    
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

    # Title Truncation for Anime/Implicit Formats
    # If we found an episode but the title still contains it (because we didn't split on SxxExx),
    # we should truncate the title at the episode number.
    if episode and search_type == 'series':
        # Create variants to search for: " 029 ", " 29 "
        # We search for the episode number surrounded by spaces or separators
        ep_str = str(int(episode))
        ep_patterns = [
            rf'\s0*{ep_str}\s',      # " 029 " or " 29 "
            rf'[-_]0*{ep_str}[-_]',  # "_029_"
            rf'\s-\s0*{ep_str}',     # " - 029"
        ]

        for pat in ep_patterns:
            match = re.search(pat, clean_t)
            if match:
                # Truncate title at the start of the match
                potential_t = clean_t[:match.start()].strip()
                if len(potential_t) >= 2:
                    clean_t = potential_t
                    break

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

    # Aggressive Series Logic (Legacy/Fallback)
    # Only runs if we found NO episode yet.
    if search_type == 'series' and episode is None:
        # Regex for trailing number: spaces, then digits, then end of string
        # Strict check: ensure it's not the ONLY thing (avoid "1899")
        match = re.search(r'\s(\d{1,4})$', clean_t)
        if match:
            found_ep = int(match.group(1))
            potential_title = clean_t[:match.start()].strip()

            # Safety Check: Title shouldn't be empty or just symbols
            # Also ensure title isn't just digits (like "1899" -> empty remainder if matched, or check original)
            if len(potential_title) >= 2 and not potential_title.isdigit():
                episode = found_ep
                season = 1 # Default to S01
                clean_t = potential_title

    # STRICT SEASON RULE: If Series mode and no Season found, force S01
    if search_type == 'series' and season is None and episode is not None:
        season = 1

    # Extract new fields
    source = extract_source(full_meta_text) or extract_source(raw_text)
    codec = extract_codec(full_meta_text) or extract_codec(raw_text)
    audio = extract_audio(full_meta_text) or extract_audio(raw_text)

    # Force strict Movie rules: No S/E logic allowed
    if search_type == 'movie':
        season = None
        episode = None

    # Special handling for "One Piece"
    if clean_t and clean_t.lower() == "one piece" and year is None:
        year = 1999

    return MediaInfo(clean_t, year, resolution, season, episode, source, audio, codec)
