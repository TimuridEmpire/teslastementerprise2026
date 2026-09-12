import math

class ScientificCalculator:
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b

    def multiply(self, a, b):
        return a * b

    def divide(self, a, b):
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

    def power(self, a, b):
        return a ** b

    def sqrt(self, a):
        if a < 0:
            raise ValueError("Square root of negative number is not defined")
        return math.sqrt(a)

    def sin(self, a):
        return math.sin(math.radians(a))

    def cos(self, a):
        return math.cos(math.radians(a))

    def tan(self, a):
        return math.tan(math.radians(a))

    def log10(self, a):
        if a <= 0:
            raise ValueError("Logarithm of non-positive number is not defined")
        return math.log10(a)

    def ln(self, a):
        if a <= 0:
            raise ValueError("Logarithm of non-positive number is not defined")
        return math.log(a)

if __name__ == "__main__":
    calc = ScientificCalculator()
    print(calc.add(2, 3))
    print(calc.subtract(5, 2))
    print(calc.multiply(4, 5))
    print(calc.divide(10, 2))
    print(calc.power(2, 3))
    print(calc.sqrt(16))
    print(calc.sin(30))
    print(calc.cos(45))
    print(calc.tan(60))
    print(calc.log10(100))
    print(calc.ln(math.e))