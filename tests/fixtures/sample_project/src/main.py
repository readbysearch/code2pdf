#!/usr/bin/env python3
"""Main module for the sample project."""

def main():
    """Entry point for the application."""
    print("Hello, World!")
    result = calculate_sum(5, 3)
    print(f"The sum of 5 and 3 is: {result}")

def calculate_sum(a, b):
    """Calculate the sum of two numbers."""
    return a + b

if __name__ == "__main__":
    main()