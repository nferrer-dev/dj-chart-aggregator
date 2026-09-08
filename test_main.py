import unittest
from unittest.mock import patch, Mock
from main import search_beatport_charts
import os

class TestMain(unittest.TestCase):
    @patch('main.requests.get')
    def test_search_beatport_charts(self, mock_get):
        # Mock the Jina Reader response using the saved markdown file
        mock_response = Mock()
        mock_response.status_code = 200
        
        with open('jina_output.md', 'r', encoding='utf-8') as f:
            mock_response.text = f.read()
            
        mock_get.return_value = mock_response

        # Test extraction for a single artist
        artists = ["Adam Port"]
        results = search_beatport_charts(artists)
        
        self.assertEqual(len(results), 25, "Should extract exactly 25 charts from the mocked markdown")
        
        # Verify the structure of the first extracted result
        first_result = results[0]
        self.assertEqual(first_result['title'], "Adam Brown Adam Brown")
        self.assertTrue(first_result['link'].startswith("https://www.beatport.com/chart/adam-brown/"))
        self.assertTrue(first_result['image_url'].startswith("https://geo-media.beatport.com/"))
        self.assertEqual(first_result['snippet'], "Chart curated by Adam Port")

if __name__ == '__main__':
    unittest.main()
