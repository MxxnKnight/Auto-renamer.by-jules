import re
import os
from config import SPAM_KEYWORDS, CAPTION_TEMPLATE

class MediaInfo:
    def __init__(self, title, year=None, resolution="720p", season=None, episode=None,
                 source=None, audio=None, codec=None, is_series=False):
        self.title = title.strip().replace(" ", ".")
        self.year = year
        self.resolution = resolution or "720p"
        self.season = season
        self.episode = episode
        self.source = source
        self.audio = audio
        self.codec = codec
        self.is_series = is_series

    def __str__(self):
        # Strictly format: Title.Year.Resolution.S00E00
        # Replace spaces with dots in title
        title_dots = self.title.replace(" ", ".")
        
        parts = [title_dots]
        if self.year:
            parts.append(str(self.year))
        
        # Ensure resolution has 'p' if numeric
        res = self.resolution
        if res.isdigit():
            res = f"{res}p"
        parts.append(res)
        
        if self.is_series:
            if self.season is not None and self.episode is not None:
                if isinstance(self.episode, list):
                    # Handle multi-part
                    ep_str = f"S{int(self.season):02d}E{int(self.episode[0]):02d}-E{int(self.episode[-1]):02d}"
                else:
                    ep_str = f"S{int(self.season):02d}E{int(self.episode):02d}"
                parts.append(ep_str)
            elif self.episode is not None:
                if isinstance(self.episode, list):
                    ep_str = f"S01E{int(self.episode[0]):02d}-E{int(self.episode[-1]):02d}"
                else:
                    ep_str = f"S01E{int(self.episode):02d}"
                parts.append(ep_str)

        return ".".join(parts)

def clean_title(title):
    # 1. Remove URLs (refined to avoid over-greediness in filenames)
    title = re.sub(r'https?://\S+', '', title)
    title = re.sub(r'www\.[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}', '', title)
    title = re.sub(r'\b\S+\.(com|org|net|in|co|me|info|io|biz|site|xyz|top|cloud|online)\b', '', title, flags=re.IGNORECASE)

    # 2. Replace common filename separators with spaces EARLY
    # This prevents handles like @Join_Our_Channel_Title from eating the title
    title = title.replace("_", " ").replace(".", " ")

    # 3. Remove Telegram Handles and Links
    title = re.sub(r'@[a-zA-Z0-9_]+', '', title)
    title = re.sub(r't\.me/\S+', '', title)

    # 4. Remove Hashtags
    title = re.sub(r'#\w+', '', title)

    # 5. Remove content in brackets [] or ()
    title = re.sub(r'\[.*?\]', '', title)
    title = re.sub(r'\(.*?\)', '', title)
    
    # 6. Handle "Prefix - Title"
    if ' - ' in title:
        segments = title.split(' - ')
        if len(segments[0]) < 15 or any(k.lower() in segments[0].lower() for k in ["Join", "Update", "Channel"]):
            title = segments[-1]

    # 7. Replace non-alphanumeric (except space) with space
    title = re.sub(r'[^a-zA-Z0-9\s]', ' ', title)
    
    # 8. Remove Spam Keywords
    for keyword in sorted(SPAM_KEYWORDS, key=len, reverse=True):
        pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
        title = pattern.sub(' ', title)

    # 9. Final Clean up
    title = re.sub(r'\s+', ' ', title).strip()
    
    # Remove trailing resolution-like things
    title = re.sub(r'\b(480p|720p|1080p|2160p|4k|8k)\b', '', title, flags=re.IGNORECASE)
    
    return title.strip()

def extract_resolution(text):
    res_pattern = r'\b(\d{3,4}p|4k|8k)\b'
    match = re.search(res_pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return None

def extract_season_episode(text):
    # Multi-part E01-02
    match = re.search(r'S(\d+)\s?E(\d+)-E(\d+)', text, re.IGNORECASE)
    if match:
        return int(match.group(1)), [int(match.group(2)), int(match.group(3))]

    # Standard S01E01
    match = re.search(r'S(\d{1,2})\s?E(\d{1,3})(?!\d|p)', text, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))
    
    # 1x01
    match = re.search(r'(\d{1,2})x(\d{1,3})(?!\d|p)', text, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))
    
    # Ep 1 / Episode 1
    match = re.search(r'(?:Episode|Ep)\s?\.?(\d{1,4})', text, re.IGNORECASE)
    if match:
        return None, int(match.group(1))

    return None, None

def find_metadata_split(text):
    # Try to find where metadata starts (Year, S01, 720p)
    year_match = re.search(r'(?<!\d)(19|20)\d{2}(?!\d)', text)
    if year_match:
        return year_match.start(), year_match.group(0)
    
    se_match = re.search(r'(S\d+|Ep\s?\d+|\d+x\d+)', text, re.IGNORECASE)
    if se_match:
        return se_match.start(), None
        
    res_match = re.search(r'(\d{3,4}p|4k|8k)', text, re.IGNORECASE)
    if res_match:
        return res_match.start(), None
        
    return -1, None

def parse_media_info(filename, caption=None, search_type=None):
    # Strip extension
    base_name, ext = os.path.splitext(filename)
    raw_text = base_name if ext.lower() in ['.mkv', '.mp4', '.avi', '.flv', '.mov', '.wmv', '.webm'] else filename
    
    # Priority: Caption often has cleaner metadata if it exists
    combined_text = (caption or "") + " " + raw_text
    
    split_idx, found_year_str = find_metadata_split(raw_text)
    
    year = int(found_year_str) if found_year_str else None
    title_part = raw_text
    if split_idx != -1:
        title_part = raw_text[:split_idx]
    
    # If title part is empty or too short, try to get title from first line of caption
    clean_t = clean_title(title_part)
    if len(clean_t) < 2 and caption:
        first_line = caption.split('\n')[0]
        clean_t = clean_title(first_line)

    resolution = extract_resolution(combined_text) or "720p"
    season, episode = extract_season_episode(combined_text)
    
    # Secondary Year Search in combined text if not found in raw title
    if not year:
        year_match = re.search(r'(?<!\d)(19|20)\d{2}(?!\d)', combined_text)
        if year_match:
            year = int(year_match.group(0))

    is_series = (search_type == 'series')
    
    return MediaInfo(clean_t, year, resolution, season, episode, is_series=is_series)
