import unittest
from src.main import calculate_sum

class TestMain(unittest.TestCase):
    """Test cases for main module."""
    
    def test_calculate_sum(self):
        """Test the calculate_sum function."""
        self.assertEqual(calculate_sum(2, 3), 5)
        self.assertEqual(calculate_sum(-1, 1), 0)
        self.assertEqual(calculate_sum(0, 0), 0)
    
    def test_calculate_sum_with_floats(self):
        """Test calculate_sum with float values."""
        self.assertAlmostEqual(calculate_sum(1.5, 2.5), 4.0)

if __name__ == '__main__':
    unittest.main()