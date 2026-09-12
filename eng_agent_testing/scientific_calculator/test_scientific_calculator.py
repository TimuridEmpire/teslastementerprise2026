import math
import unittest

from scientific_calculator import ScientificCalculator


class TestScientificCalculator(unittest.TestCase):
    def setUp(self):
        self.calc = ScientificCalculator()

    def test_basic_ops(self):
        self.assertEqual(self.calc.add(2, 3), 5)
        self.assertEqual(self.calc.subtract(5, 2), 3)
        self.assertEqual(self.calc.multiply(4, 5), 20)
        self.assertAlmostEqual(self.calc.divide(10, 2), 5)

    def test_divide_by_zero_raises(self):
        with self.assertRaises(ValueError):
            self.calc.divide(1, 0)

    def test_power_and_sqrt(self):
        self.assertEqual(self.calc.power(2, 3), 8)
        self.assertAlmostEqual(self.calc.sqrt(16), 4)
        with self.assertRaises(ValueError):
            self.calc.sqrt(-1)

    def test_trig_degrees(self):
        self.assertAlmostEqual(self.calc.sin(30), 0.5, places=5)
        self.assertAlmostEqual(self.calc.cos(60), 0.5, places=5)
        self.assertAlmostEqual(self.calc.tan(45), 1.0, places=5)

    def test_logs(self):
        self.assertAlmostEqual(self.calc.log10(100), 2)
        self.assertAlmostEqual(self.calc.ln(math.e), 1)
        with self.assertRaises(ValueError):
            self.calc.log10(0)
        with self.assertRaises(ValueError):
            self.calc.ln(-5)


if __name__ == "__main__":
    unittest.main()
