# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains two command-line tools:
- **code2pdf**: Converts source code files to PDF format with syntax highlighting and table of contents. Uses Vim for syntax highlighting and Ghostscript for PDF operations.
- **code2txt**: Combines source code files into a single markdown-formatted text file optimized for LLM context input, with table of contents and syntax highlighting.

## Architecture

The project consists of:

### Entry Points
- **`bin/code2pdf`** - PDF conversion tool with dependency checking and routing
- **`bin/code2txt`** - Text combination tool with flexible filtering options

### Processing Scripts
- **`scripts/print_single_file_to_pdf.sh`** - Converts individual files to PDF
- **`scripts/print_all.sh`** - Recursively processes directories for PDF generation
- **`scripts/combine_to_txt.sh`** - Combines files into markdown-formatted text

### Configuration
- **`config/vimrc`** - Vim configuration for consistent syntax highlighting (PDF only)

## Key Components

### code2pdf (`bin/code2pdf`)
- Supports development mode via `--dev` flag that switches between brew installation path and local development path
- Performs dependency checking for `vim`, `gs` (ghostscript), and `jq`
- Routes to appropriate processing script based on `-s` (single file) or `-a` (all files) options
- Defines default filtering rules for directory processing

### code2txt (`bin/code2txt`)
- Parses command-line arguments for flexible configuration
- Validates input directories and converts to absolute paths
- Supports file filtering (ignore-types, include-types, ignore-folders)
- Configurable file size limits with human-readable formats (K, M, G)
- Optional table of contents generation
- Verbose mode for debugging

### PDF Directory Processing (`scripts/print_all.sh`)
- Uses JSON configuration for blacklisted folders, file extensions, and special files
- Implements symbolic link recursion prevention using visited directories tracking
- Generates unique PDF filenames by transforming file paths (e.g., `src/file.js` → `src____file----js.pdf`)
- Creates table of contents from processed files
- Merges all PDFs into final `merged.pdf` using Ghostscript

### Text Combination (`scripts/combine_to_txt.sh`)
- Directory traversal with symbolic link protection
- Language detection for markdown syntax highlighting
- Cross-platform file size checking (macOS/Linux)
- Sorted file output for consistent results
- Markdown formatting with code blocks
- Handles files without extensions (Dockerfile, Makefile, etc.)

### Single File PDF Processing (`scripts/print_single_file_to_pdf.sh`)
- Converts individual files using Vim hardcopy feature
- Uses PostScript intermediate format before PDF conversion

## Development Commands

### Testing code2pdf
```bash
# Test single file conversion
./bin/code2pdf --dev -s path/to/file.py

# Test directory conversion  
./bin/code2pdf --dev -a path/to/directory

# Check dependencies
./bin/code2pdf --help
```

### Testing code2txt
```bash
# Test with default settings
./bin/code2txt

# Test with specific file types
./bin/code2txt --include-types js,ts src/

# Test with verbose output
./bin/code2txt --verbose -o output.txt .

# Test file size limits
./bin/code2txt --max-file-size 100K src/

# Check all options
./bin/code2txt --help
```

### Running Automated Tests
```bash
# Set up test environment
python3 -m venv test_venv
source test_venv/bin/activate
pip install -r requirements-test.txt

# Run all tests
pytest

# Run specific test suites
pytest tests/test_code2txt.py  # Test code2txt functionality
pytest tests/test_code2pdf.py  # Test code2pdf functionality
pytest tests/test_integration.py  # Run integration tests

# Run with verbose output
pytest -v

# Run specific test
pytest tests/test_code2txt.py::TestCode2txt::test_help_option
```

### Development Mode
Use `--dev` flag to use local development directory instead of brew installation path. The development path is hardcoded to `/Users/<you>/git/code2pdf` in the main script.

### Dependencies Required

For code2pdf:
- `vim` - For syntax highlighting and hardcopy generation
- `gs` (ghostscript) - For PostScript to PDF conversion and PDF merging
- `jq` - For JSON processing of configuration parameters

For code2txt:
- No external dependencies (pure bash)

## File Processing Logic

### code2pdf Default Filtering Rules
- **Blacklisted folders**: `node_modules`, `.git`, `dist`, `out`
- **Blacklisted patterns**: `env*`
- **Whitelisted extensions**: `rb`, `sh`, `md`, `js`, `py`, `ts`, `java`, `cpp`, `h`, `c`, `html`
- **Whitelisted filenames**: `README`, `LICENSE`, `Makefile`, `launch.json`
- **Include files without extensions**: `true` (for Dockerfile, etc.)

### code2txt Default Filtering Rules
- **Ignored extensions**: `bin`, `pdf`, `jpg`, `png`, `gif`, `zip`, `tar`, `gz`, `exe`, `dll`, `so`, `dylib`, `class`, `jar`, `war`, `ear`, `pyc`, `pyo`, `txt`
- **Ignored folders**: `node_modules`, `.git`, `dist`, `out`, `build`, `__pycache__`, `.venv`, `venv`, `env`, `.env`, `vendor`, `target`
- **Max file size**: `500K` (configurable)
- **Include-types**: When specified, overrides ignore-types and only processes specified extensions

### code2pdf Processing Flow
1. Clean `/tmp` directory of existing PS/PDF files
2. Recursively traverse directories applying filtering rules
3. Convert each qualifying file to PostScript using Vim
4. Convert PostScript to PDF using `ps2pdf`
5. Generate table of contents from processed files
6. Merge all PDFs including table of contents into `merged.pdf`

### code2txt Processing Flow
1. Parse command-line arguments and validate input directory
2. Recursively traverse directories with symbolic link protection
3. Apply filtering rules (ignore/include types, folders, file size)
4. Detect language for each file for syntax highlighting
5. Generate optional table of contents
6. Combine files with markdown formatting into output file

## Important Implementation Details

### code2pdf
- File path transformations use Perl regex: `/` → `____`, `.` → `----`
- Symbolic link recursion is prevented by tracking visited real paths
- All intermediate files are stored in `/tmp` before final merge
- Error handling includes explicit checks for PDF creation and file moves
- Debug output is sent to stderr to avoid interfering with normal operation

### code2txt
- Language detection maps file extensions to markdown language identifiers
- Cross-platform file size checking using different stat commands for macOS/Linux
- Files are sorted alphabetically for consistent output
- Table of contents is optional and placed at the beginning
- Output uses markdown code blocks with proper syntax highlighting
- Default ignores `.txt` files to prevent recursive inclusion of output file

## Testing

### Test Suite Overview
- **34 automated tests** covering both tools
- **Test framework**: pytest with subprocess-based testing
- **Test coverage**:
  - code2txt: 16 unit tests
  - code2pdf: 10 unit tests
  - Integration: 8 tests
- **Test fixtures**: Sample projects and edge cases in `tests/fixtures/`
- **Configuration**: `pytest.ini` excludes fixture directories from test discovery

### Test Categories
1. **Functionality tests**: Command-line parsing, file filtering, output generation
2. **Edge case tests**: Empty files, special characters, large files, symbolic links
3. **Performance tests**: Large repositories, many files
4. **Integration tests**: Both tools on same data, consistency checks

### Running Tests
See `tests/README.md` for detailed testing instructions. Basic usage:
```bash
pytest  # Run all tests
pytest -v  # Verbose output
pytest tests/test_code2txt.py  # Run specific test file
```