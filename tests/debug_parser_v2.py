import re
from config import SPAM_KEYWORDS

def clean_title_debug(title):
    print(f"Original: '{title}'")
    
    r1 = r'https?://\S+'
    if re.search(r1, title):
        print(f"Matched r1: {re.search(r1, title).group(0)}")
    title = re.sub(r1, '', title)
    
    r2 = r'www\.[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}'
    if re.search(r2, title):
        print(f"Matched r2: {re.search(r2, title).group(0)}")
    title = re.sub(r2, '', title)
    
    r3 = r'\b\S+\.(com|org|net|in|co|me|info|io|biz|site|xyz|top|cloud|online)\b'
    if re.search(r3, title, flags=re.IGNORECASE):
        print(f"Matched r3: {re.search(r3, title, flags=re.IGNORECASE).group(0)}")
    title = re.sub(r3, '', title, flags=re.IGNORECASE)
    
    print(f"After Step 1: '{title}'")
    return title

if __name__ == "__main__":
    clean_title_debug("Spam_Link_www.movies.com_The.Matrix.")
