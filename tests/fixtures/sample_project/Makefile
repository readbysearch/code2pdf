.PHONY: help build test clean run

help:
	@echo "Available commands:"
	@echo "  make build  - Build the project"
	@echo "  make test   - Run tests"
	@echo "  make clean  - Clean build artifacts"
	@echo "  make run    - Run the application"

build:
	@echo "Building project..."
	python -m py_compile src/*.py

test:
	@echo "Running tests..."
	python -m pytest tests/

clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

run:
	@echo "Running application..."
	python src/main.py