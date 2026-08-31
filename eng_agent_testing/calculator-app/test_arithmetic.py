import unittest
from arithmetic import add, subtract, multiply, divide

class TestArithmetic(unittest.TestCase):

    def test_add(self):
        self.assertEqual(add(8, 9), 17)
        self.assertEqual(add(-4, 6), 2)
        self.assertEqual(add(0, -3), -3)

    def test_subtract(self):
        self.assertEqual(subtract(10, 6), 4)
        self.assertEqual(subtract(5, 8), -3)
        self.assertEqual(subtract(-2, -5), 3)

    def test_multiply(self):
        self.assertEqual(multiply(7, 9), 63)
        self.assertEqual(multiply(-4, 6), -24)
        self.assertEqual(multiply(0, -3), 0)

    def test_divide(self):
        self.assertEqual(divide(8, 4), 2)
        self.assertEqual(divide(-15, 3), -5)
        self.assertEqual(divide(8, -4), -2)
        with self.assertRaises(ValueError):
            divide(4, 0)

if __name__ == '__main__':
    unittest.main()