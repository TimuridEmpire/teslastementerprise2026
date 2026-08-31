# main.py

import sys
from arithmetic import add, subtract, multiply, divide

def run_calculator():
    while True:
        try:
            num1 = float(input("Enter first number: "))
            num2 = float(input("Enter second number: "))
            operation = input("Choose an operation (+, -, *, /): ")

            if operation == '+':
                result = add(num1, num2)
            elif operation == '-':
                result = subtract(num1, num2)
            elif operation == '*':
                result = multiply(num1, num2)
            elif operation == '/':
                result = divide(num1, num2)
            else:
                print("Invalid operation")
                continue

            print(f"Result: {result}")
        except ValueError as e:
            print("Please enter valid numbers.")
        except ZeroDivisionError as e:
            print(e)
        
        another_calculation = input("Would you like to perform another calculation? (yes/no): ")
        if another_calculation.lower() != 'yes':
            break

if __name__ == '__main__':
    run_calculator()