import unittest
import sys
import os

# Add parent directory to path to import media_parser
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from media_parser import parse_media_info

class TestMediaParserVariants(unittest.TestCase):
    def test_series_aggressive_extraction(self):
        # Case 1: "One Piece 236" -> Expect Title "One Piece", Episode 236
        filename = "One Piece 236 720p.mkv"
        info = parse_media_info(filename, search_type='series')
        self.assertEqual(info.title, "One Piece")
        self.assertEqual(info.episode, 236)
        self.assertEqual(info.season, 1) # Default S1

    def test_series_aggressive_extraction_no_res(self):
        # Case 1b: "One Piece 236" -> Expect Title "One Piece", Episode 236
        filename = "One Piece 236.mkv"
        info = parse_media_info(filename, search_type='series')
        self.assertEqual(info.title, "One Piece")
        self.assertEqual(info.episode, 236)

    def test_series_standard(self):
        # Case 2: "Stranger Things S01E01"
        filename = "Stranger Things S01E01.mkv"
        info = parse_media_info(filename, search_type='series')
        self.assertEqual(info.title, "Stranger Things")
        self.assertEqual(info.episode, 1)
        self.assertEqual(info.season, 1)

    def test_movie_strict(self):
        # Case 3: "Inception 2010"
        filename = "Inception 2010.mkv"
        info = parse_media_info(filename, search_type='movie')
        self.assertEqual(info.title, "Inception")
        self.assertEqual(info.year, 2010)
        # Ensure no episode detected even if there are numbers (though unlikely here)

    def test_movie_numeric_title(self):
        # Case 4: "1917"
        filename = "1917.mkv"
        info = parse_media_info(filename, search_type='movie')
        self.assertEqual(info.title, "1917")
        self.assertIsNone(info.episode)

    def test_series_numeric_title_safety(self):
        # Case 5: "1899" -> Should not extract 1899 as Episode because title would be empty
        filename = "1899.mkv"
        info = parse_media_info(filename, search_type='series')
        self.assertEqual(info.title, "1899")
        self.assertIsNone(info.episode)

    def test_series_space_separated_ep(self):
         # User Example: "one piece 236 720p"
         filename = "one piece 236 720p.mkv"
         info = parse_media_info(filename, search_type='series')
         self.assertEqual(info.title.lower(), "one piece")
         self.assertEqual(info.episode, 236)

    def test_legacy_one_piece(self):
        filename = "[SubGroup] One Piece - 1015 [1080p].mkv"
        info = parse_media_info(filename)
        self.assertEqual(info.episode, 1015)

if __name__ == '__main__':
    unittest.main()
