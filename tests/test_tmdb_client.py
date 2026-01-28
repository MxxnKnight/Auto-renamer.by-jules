import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Add repo root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tmdb_client import TMDBClient

class TestTMDBClient(unittest.TestCase):
    def setUp(self):
        # Mock environment variables
        self.patcher = patch.dict(os.environ, {"TMDB_API_KEY": "fake_key"})
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    @patch('tmdb_client.TMDb')
    @patch('tmdb_client.Movie')
    @patch('tmdb_client.TV')
    def test_search_media_returns_none_when_string_returned(self, MockTV, MockMovie, MockTMDb):
        # Setup mocks
        mock_tv_instance = MockTV.return_value

        # Simulate tmdbv3api returning a list of strings (iterating keys case)
        # tmdbv3api objects iterate over results, but if keys are iterated, we get strings.
        mock_tv_instance.search.return_value = ["page", "results"]

        client = TMDBClient()

        # Act
        result = client.search_media("Naruto", is_series=True)

        # Assert
        # Should return None because "page" is a string and should be rejected
        self.assertIsNone(result)

        # Verify search was called
        mock_tv_instance.search.assert_called_with("Naruto")

    @patch('tmdb_client.TMDb')
    @patch('tmdb_client.Movie')
    @patch('tmdb_client.TV')
    def test_search_media_normal_behavior(self, MockTV, MockMovie, MockTMDb):
        mock_tv_instance = MockTV.return_value

        # Simulate normal result
        # Use spec to ensure accessing 'title' raises AttributeError so get_attr falls back to 'name'
        mock_result = MagicMock(spec=['name', 'first_air_date', 'overview', 'id'])
        mock_result.name = "Naruto"
        mock_result.first_air_date = "2002-10-03"
        mock_result.overview = "Ninja stuff"
        mock_result.id = 123

        mock_tv_instance.search.return_value = [mock_result]

        client = TMDBClient()
        result = client.search_media("Naruto", is_series=True)

        self.assertIsNotNone(result)
        self.assertEqual(result['title'], "Naruto")
        self.assertEqual(result['year'], 2002)

if __name__ == '__main__':
    unittest.main()
