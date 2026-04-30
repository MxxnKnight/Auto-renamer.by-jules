import re
from config import SPAM_KEYWORDS

def clean_title_debug(title):
    print(f"Original: '{title}'")
    # 1. Remove URLs
    title = re.sub(r'https?://\S+', '', title)
    title = re.sub(r'www\.\S+', '', title)
    title = re.sub(r'\S+\.(com|org|net|in|co|me|info|io|biz|site|xyz|top|cloud|online)\b', '', title, flags=re.IGNORECASE)
    print(f"Step 1 (URLs): '{title}'")

    # 2. Remove Telegram Handles and Links
    title = re.sub(r'@[a-zA-Z0-9_]+', '', title)
    title = re.sub(r't\.me/\S+', '', title)
    print(f"Step 2 (Handles): '{title}'")

    # 3. Remove Hashtags
    title = re.sub(r'#\w+', '', title)
    print(f"Step 3 (Hashtags): '{title}'")

    # 4. Remove content in brackets
    title = re.sub(r'\[.*?\]', '', title)
    print(f"Step 4 (Brackets): '{title}'")
    
    # 5. Handle "Prefix - Title"
    if ' - ' in title:
        segments = title.split(' - ')
        if len(segments[0]) < 15 or any(k.lower() in segments[0].lower() for k in ["Join", "Update", "Channel"]):
            title = segments[-1]
    print(f"Step 5 (Prefix): '{title}'")

    # 6. Replace non-alphanumeric
    title = re.sub(r'[^a-zA-Z0-9\s]', ' ', title)
    print(f"Step 6 (Non-Alpha): '{title}'")
    
    # 7. Remove Spam Keywords
    for keyword in sorted(SPAM_KEYWORDS, key=len, reverse=True):
        pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
        title = pattern.sub(' ', title)
    print(f"Step 7 (Spam): '{title}'")

    # 8. Final Clean up
    title = re.sub(r'\s+', ' ', title).strip()
    print(f"Step 8 (Final): '{title}'")
    
    return title

if __name__ == "__main__":
    clean_title_debug("Spam_Link_www.movies.com_The.Matrix.")
    print("="*30)
    clean_title_debug("@Join_Our_Channel_The.Dark.Knight.")
