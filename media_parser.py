import re
from config import SPAM_KEYWORDS

class MediaInfo:
    def __init__(self, title, year=None, resolution="720p", season=None, episode=None):
        self.title = title.strip()
        self.year = year
        self.resolution = resolution
        self.season = season
        self.episode = episode

    def __str__(self):
        # Format: Title Year Resolution S00E00
        parts = [self.title]
        if self.year:
            parts.append(str(self.year))
        
        parts.append(self.resolution)
        
        if self.season is not None and self.episode is not None:
            parts.append(f"S{int(self.season):02d}E{int(self.episode):02d}")
        elif self.episode is not None:
            # If only episode is found, default to Season 1
            parts.append(f"S01E{int(self.episode):02d}")
            
        return " ".join(parts)

def clean_title(title):
    # 1. Remove URLs
    title = re.sub(r'https?://\S+', '', title)

    # 2. Handle Telegram Handles specifically
    # If title starts with @, it's likely a handle-prefixed filename
    if title.startswith('@'):
        # Normalize separators to space for easier splitting, but keep track of parts
        # Actually, let's split by common separators
        parts = re.split(r'[ ._]+', title)

        # Remove the first part (the main handle, e.g. @WMR)
        if parts and parts[0].startswith('@'):
            parts.pop(0)

        # Heuristic: Remove subsequent parts if they are short (<=3 chars) and likely garbage/extension
        # UNLESS it is the ONLY part left (don't delete the movie name if it's short like "Up")
        while parts and len(parts) > 1 and len(parts[0]) <= 3:
            parts.pop(0)

        title = " ".join(parts)
    else:
        # Standard handle removal for mid-sentence handles
        title = re.sub(r'@[a-zA-Z0-9_]+', '', title)

    # 3. Remove content in square brackets [] globally
    title = re.sub(r'\[.*?\]', '', title)

    # 4. Remove dots, underscores (Replace with space)
    title = title.replace(".", " ").replace("_", " ")
    
    # Remove custom spam keywords
    # Sort by length descending to replace longer phrases first
    # Case insensitive replacement
    for keyword in sorted(SPAM_KEYWORDS, key=len, reverse=True):
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        title = pattern.sub(' ', title)

    # Remove starting non-alphanumeric chars (generic)
    title = re.sub(r'^[^a-zA-Z0-9]+', '', title)
    
    # Remove trailing non-alphanumeric chars (like '(', '[', '-', ' ')
    # Pattern: [^a-zA-Z0-9]+$ matches any non-alphanum chars at end
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
    # Priority 1: S01E01 format
    match = re.search(r'S(\d+)\s?E(\d+)', text, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))
    
    # Priority 2: 1x01 format
    match = re.search(r'(\d+)x(\d+)', text, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))
    
    # Priority 3: Episode 1 / Ep 1
    match = re.search(r'(?:Episode|Ep)\s?\.?(\d+)', text, re.IGNORECASE)
    if match:
        return None, int(match.group(1)) # No season
        
    # Priority 4: " - 123 " (Anime style) or " - 01 "
    # Must look for this carefully to avoid matching year or resolution numbers
    # Usually at end of string or before extension
    match = re.search(r'\s-\s(\d+)(?:\s|\[|\.|$)', text)
    if match:
        return None, int(match.group(1))

    # Priority 5: 1/23 (found in structured caption example)
    match = re.search(r'Episode Number:\s?(\d+)', text, re.IGNORECASE)
    if match:
        return None, int(match.group(1))

    match = re.search(r'(\d+)/(\d+)', text)
    if match and "episode" in text.lower():
         return None, int(match.group(1))

    return None, None

def find_metadata_split(text):
    # Returns the index where metadata likely starts
    # Keywords: Year, Resolution, SxxExx
    
    # Check Year first
    # Improved regex to handle boundaries like _ or . (negative lookaround for digits)
    year_match = re.search(r'(?<!\d)(19|20)\d{2}(?!\d)', text)
    if year_match:
        return year_match.start(), year_match.group(0)
        
    # Check Season/Episode
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
            
    # Check Resolution
    res_match = re.search(r'(\d{3,4}p|4k|8k)', text, re.IGNORECASE)
    if res_match:
        return res_match.start(), None
        
    return -1, None

def parse_media_info(filename, caption=None):
    raw_text = filename
    
    # Structured Caption Override Check
    # If caption implies a totally different title (e.g. filename is gibberish),
    # we might want to use caption as primary. 
    # But sticking to the plan: parse filename, use caption for missing bits.
    
    # 1. Determine Split Point
    split_idx, found_year_str = find_metadata_split(raw_text)
    
    year = int(found_year_str) if found_year_str else None
    title_part = raw_text
    meta_part = ""
    
    if split_idx != -1:
        title_part = raw_text[:split_idx]
        if found_year_str:
             # If split by year, meta starts AFTER year (length 4)
             meta_part = raw_text[split_idx+4:]
        else:
             # If split by other meta, meta starts AT split_idx
             meta_part = raw_text[split_idx:]
    else:
        # No metadata found in filename?
        # Maybe whole thing is title
        pass

    # 2. Extract Resolution (from meta_part if split, else whole)
    resolution = extract_resolution(meta_part if split_idx != -1 else raw_text) or "720p"
    
    # 3. Extract Season/Episode
    season, episode = extract_season_episode(meta_part if split_idx != -1 else raw_text)
    
    # 4. Fallbacks from Caption
    if caption:
        if not season and not episode:
             s_e_cap = extract_season_episode(caption)
             if s_e_cap != (None, None):
                 season, episode = s_e_cap
        
        if (not resolution or resolution == "720p") and "720p" not in (meta_part or raw_text):
             # Only override default if we actually found something in caption
             res_cap = extract_resolution(caption)
             if res_cap:
                 resolution = res_cap
                 
        if not year:
            y_cap = re.search(r'(\b(19|20)\d{2}\b)', caption)
            if y_cap:
                year = int(y_cap.group(1))
                
        # Special Case: Structured Caption "Series: Title" override
        series_match = re.search(r'Series:\s?(.*)', caption, re.IGNORECASE)
        if series_match:
            title_part = series_match.group(1).strip()
            # If we took title from caption, we should rely on caption for year too probably,
            # but we already parsed year from caption if missing.

    # 5. Clean Title
    clean_t = clean_title(title_part)
    
    # Fallback: if title is empty
    if not clean_t:
        # If split failed or consumed everything, try raw
        clean_t = clean_title(raw_text)

    return MediaInfo(clean_t, year, resolution, season, episode)
