from media_parser import parse_media_info

def test_parser():
    test_cases = [
        # Movie cases
        {
            "filename": "Inception.2010.1080p.BluRay.x264.mkv",
            "caption": "Download Inception (2010) @movies_channel",
            "type": "movie",
            "expected": "Inception.2010.1080p"
        },
        {
            "filename": "Spam_Link_www.movies.com_The.Matrix.1999.720p.mkv",
            "caption": "The Matrix (1999) - High Quality",
            "type": "movie",
            "expected": "The.Matrix.1999.720p"
        },
        # Series cases
        {
            "filename": "One.Piece.S01E1015.720p.WEBRip.mkv",
            "caption": "One Piece Episode 1015 @anime_links",
            "type": "series",
            "expected": "One.Piece.2024.720p.S01E1015" # 2024 if TMDB not mocked, but let's see local parse
        },
        {
            "filename": "Stranger.Things.S04E01-E02.1080p.mkv",
            "caption": "Stranger Things S04 E01-02",
            "type": "series",
            "expected": "Stranger.Things.1080p.S04E01-E02"
        },
        # Spam/Handle cases
        {
            "filename": "@Join_Our_Channel_The.Dark.Knight.2008.mkv",
            "caption": "https://t.me/spam_link The Dark Knight",
            "type": "movie",
            "expected": "The.Dark.Knight.2008.720p"
        }
    ]

    print("Running Parser Tests...\n")
    for case in test_cases:
        info = parse_media_info(case["filename"], case["caption"], search_type=case["type"])
        result = str(info)
        print(f"Input: {case['filename']}")
        print(f"Output: {result}")
        print("-" * 20)

if __name__ == "__main__":
    test_parser()
