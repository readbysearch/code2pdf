# Testing Guide for code2pdf and code2txt

This directory contains the test suite for both `code2pdf` and `code2txt` tools.

## Setup

1. Create a virtual environment:
```bash
python3 -m venv test_venv
source test_venv/bin/activate  # On macOS/Linux
```

2. Install test dependencies:
```bash
pip install -r requirements-test.txt
```

## Running Tests

### Run all tests:
```bash
pytest
```

### Run specific test file:
```bash
pytest tests/test_code2txt.py
pytest tests/test_code2pdf.py
pytest tests/test_integration.py
```

### Run with verbose output:
```bash
pytest -v
```

### Run specific test:
```bash
pytest tests/test_code2txt.py::TestCode2txt::test_help_option
```

### Run with timeout (prevent hanging tests):
```bash
pytest --timeout=30
```

## Test Structure

- **test_code2txt.py**: Unit tests for code2txt functionality
  - Command-line argument parsing
  - File filtering (ignore-types, include-types)
  - Folder filtering
  - File size limits
  - Table of contents generation
  - Language detection
  - Error handling

- **test_code2pdf.py**: Unit tests for code2pdf functionality
  - Dependency checking
  - Single file conversion
  - Directory conversion
  - Error handling

- **test_integration.py**: Integration tests for both tools
  - Large repository simulation
  - Mixed content types
  - Unicode handling
  - Performance tests
  - Consistency checks

## Test Fixtures

The `fixtures/` directory contains sample files for testing:
- **sample_project/**: A complete project with multiple file types
- **edge_cases/**: Files for testing edge cases (empty files, special characters, large files)
- **empty_dir/**: Empty directory for testing

## Notes

- Some code2pdf tests may be skipped if dependencies (vim, ghostscript, jq) are not installed
- Tests are designed to work on both Linux and macOS
- The test suite uses subprocess to test the actual bash scripts