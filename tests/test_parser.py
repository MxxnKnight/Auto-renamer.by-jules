import unittest
import sys
import os

# Add parent directory to path to import media_parser
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from media_parser import parse_media_info

class TestParser(unittest.TestCase):
    def test_movie_example_1(self):
        filename = "The Walk 2015 720p Hindi English MoviesFlix org in mkv 887.50 MB"
        info = parse_media_info(filename, search_type='movie')
        self.assertEqual(str(info), "The Walk 2015 720p Hindi English")
        
    def test_movie_example_2(self):
        filename = "Alpha 2025 1080p WEBRip x264 AAC5 1-[YTS LT].mp4"
        info = parse_media_info(filename, search_type='movie')
        self.assertEqual(str(info), "Alpha 2025 1080p WEBRip x264 AAC")
        
    def test_movie_example_3(self):
        # User output expectation: In His Steps 2013 [Resolution]
        # Filename has "HQ HDRip" but no explicit "720p" or "1080p".
        # Parser defaults to 720p if not found.
        filename = "🇹‌𝐏 - In His Steps (2013) HQ HDRip - x264 - [Tamil Dub] - (AAC 2.0) - 350MB - ESub"
        info = parse_media_info(filename, search_type='movie')
        self.assertEqual(str(info), "In His Steps 2013 720p HDRIP x264 Tamil AAC ESub")

    def test_series_structured_caption(self):
        filename = "Jujutsu_Kaisen_Ep1.mkv" # Dummy filename
        caption = """Series: Jujutsu Kaisen
○ Language: English
○ Resolution: 720p
○ Codec: H.264
○ Episode Title: Hidden Inventory
○ Episode Number: 1/23
○ Released on: 2023-07-06
○ Episode Rating: 8.0 (5200)"""
        info = parse_media_info(filename, caption, search_type='series')
        # Should detect "Jujutsu Kaisen" from caption, Year 2023 from caption, 
        # Resolution 720p from caption, Episode 1 from caption.
        # Season is not explicit, so defaults to S01.
        self.assertEqual(str(info), "Jujutsu Kaisen 720p S01E01 x264 English")

    def test_series_standard_filename(self):
        filename = "Breaking.Bad.S05E14.1080p.BluRay.x264.mkv"
        info = parse_media_info(filename, search_type='series')
        # Year is not in filename, so it might be missing from output if not provided.
        # Output: Breaking Bad 1080p S05E14
        self.assertEqual(str(info), "Breaking Bad 1080p S05E14 BLURAY x264")

    def test_series_one_piece(self):
        filename = "[SubGroup] One Piece - 1015 [1080p].mkv"
        info = parse_media_info(filename, search_type='series')
        # Should detect Episode 1015. Season default S01?
        # Output: One Piece 1999 1080p S01E1015 Sub
        self.assertEqual(str(info), "One Piece 1999 1080p S01E1015 Sub")
        
    def test_series_1x01(self):
        filename = "House.of.Cards.1x01.720p.mkv"
        info = parse_media_info(filename, search_type='series')
        self.assertEqual(str(info), "House of Cards 720p S01E01")
        
    def test_spam_keyword_removal(self):
        # "MoviesFlix" is in SPAM_KEYWORDS
        filename = "Spider-Man No Way Home 2021 MoviesFlix 1080p.mkv"
        info = parse_media_info(filename, search_type='movie')
        # Should remove MoviesFlix
        self.assertEqual(str(info), "Spider-Man No Way Home 2021 1080p")

if __name__ == '__main__':
    unittest.main()
