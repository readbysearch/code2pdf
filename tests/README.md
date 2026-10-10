# Testing Guide for code2pdf and code2txt

This directory contains the test suite for both `code2pdf` and `code2txt` tools.

## Setup

1. Create a virtual environment in the repo root (the launchers pick up `.venv/` automatically):
```bash
python3 -m venv .venv
source .venv/bin/activate  # On macOS/Linux
```

2. Install runtime and test dependencies:
```bash
pip install -r requirements.txt -r requirements-test.txt
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

- **test_code2txt_output.py**: code2txt never reads its own output file

- **test_launcher.py**: Launcher behaviour
  - Works through symlinks (as created by `install.sh` or `ln -s`)
  - `CODE2PDF_HOME` override and missing-scripts error
  - `--help` works without PDF dependencies

- **test_dir_to_pdf.py**: One-pass directory renderer
  - File selection identical to the old bash rules (`--list-files`)
  - Table of contents first, with page numbers that match where each file starts
  - Relative page headers, CJK, no Ghostscript needed, clear error when nothing matches

- **test_print_all_tmp.py**: Directory conversion safety
  - Leaves unrelated files in `/tmp` alone; the PDF contains only its own pages
  - Leaves no work files behind
  - Fails fast on a missing directory

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

- code2pdf tests need Pygments and WeasyPrint (in `.venv/`), and `pdftotext` (poppler) for text checks; some skip without them. Ghostscript is only used by the tests to count pages
- `bin/code2pdf` runs the scripts in this checkout, not an installed copy, so tests always exercise your working tree
- Tests are designed to work on both Linux and macOS
- The test suite uses subprocess to test the actual bash scripts