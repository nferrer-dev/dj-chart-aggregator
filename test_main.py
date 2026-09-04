import unittest
from main import chunk_list

class TestMain(unittest.TestCase):
    def test_chunk_list(self):
        items = [f"item_{i}" for i in range(132)]
        chunks = chunk_list(items, 8)
        
        self.assertEqual(len(chunks), 17) # 132 / 8 = 16.5 -> 17 chunks
        self.assertEqual(len(chunks[0]), 8)
        self.assertEqual(len(chunks[-1]), 4) # 132 % 8 = 4

if __name__ == '__main__':
    unittest.main()
