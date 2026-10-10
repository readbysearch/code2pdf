# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains two command-line tools:
- **code2pdf**: Converts source code files to PDF format with syntax highlighting and table of contents. Uses Python/Pygments for syntax highlighting with full UTF-8 and CJK support, and Ghostscript for PDF operations.
- **code2txt**: Combines source code files into a single markdown-formatted text file optimized for LLM context input, with table of contents and syntax highlighting.

## Architecture

The project consists of:

### Entry Points
- **`bin/code2pdf`** - PDF conversion tool with dependency checking and routing
- **`bin/code2txt`** - Text combination tool with flexible filtering options

### Processing Scripts
- **`scripts/code_to_pdf.py`** - Python script for converting source code to PDF with UTF-8/CJK support
- **`scripts/print_single_file_to_pdf.sh`** - Converts individual files to PDF using Python script
- **`scripts/print_all.sh`** - Recursively processes directories for PDF generation using Python script
- **`scripts/combine_to_txt.sh`** - Combines files into markdown-formatted text

### Configuration
- **`config/vimrc`** - Legacy Vim configuration (no longer used for PDF generation)

## Key Components

### code2pdf (`bin/code2pdf`)
- Supports development mode via `--dev` flag that switches between brew installation path and local development path
- Performs dependency checking for `python3`, `pygments`, `weasyprint`, `gs` (ghostscript), and `jq`
- Routes to appropriate processing script based on `-s` (single file) or `-a` (all files) options
- Defines default filtering rules for directory processing

### Python PDF Generator (`scripts/code_to_pdf.py`)
- Converts source code → HTML (with Pygments) → PDF (with WeasyPrint)
- Full UTF-8 and CJK character support
- Syntax highlighting for 500+ languages
- Configurable fonts with fallback support (Noto Sans CJK → DejaVu)
- Generates headers with file paths and page numbers

### code2txt (`bin/code2txt`)
- Parses command-line arguments for flexible configuration
- Validates input directories and converts to absolute paths
- Supports file filtering (ignore-types, include-types, ignore-folders, ignore-files)
- Configurable file size limits with human-readable formats (K, M, G)
- Optional table of contents generation
- Verbose mode for debugging

### PDF Directory Processing (`scripts/print_all.sh`)
- Uses JSON configuration for blacklisted folders, file extensions, and special files
- Implements new filtering parameters: ignore-files, ignore-types, ignore-folders, include-types
- Symbolic link recursion prevention using visited directories tracking
- Generates unique PDF filenames by transforming file paths (e.g., `src/file.js` → `src____file----js.pdf`)
- Converts files using Python script (`code_to_pdf.py`) for UTF-8/CJK support
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
- Converts individual files using Python script (`code_to_pdf.py`)
- Full UTF-8 and CJK character support
- Output goes to current working directory

## Key Technical Details

**Dependencies**:
- Python 3 with packages: pygments (syntax highlighting), weasyprint (HTML→PDF)
- Ghostscript/gs (PDF merging operations)
- jq (JSON parsing)

**Font Support**:
- Uses Noto Sans CJK fonts for Chinese/Japanese/Korean characters
- Fonts installed in `~/.local/share/fonts/noto-cjk/`
- Automatic fallback to DejaVu fonts for non-CJK text
- Monospace fonts for code: Noto Sans Mono CJK SC
- **Installation guide**: See `docs/font_installation_guide.md`
- **Quick setup**: Run `./scripts/setup_cjk_fonts.sh [sc|tc|jp|kr|all]`

**Migration from Vim to Python/Pygments**:
- Old approach used Vim hardcopy with PostScript (poor UTF-8/CJK support)
- New approach uses Python/Pygments for better UTF-8 support and 500+ languages
- `config/vimrc` retained for reference only

## Development Commands

### Testing code2pdf

To test changes without installing via Homebrew, use `--dev` flag (requires updating hardcoded path in `bin/code2pdf:8` to your local path):

```bash
./bin/code2pdf --dev -s path/to/file.py
./bin/code2pdf --dev -a path/to/directory
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

### Testing single file conversion

```bash
# Direct Python script
python3 scripts/code_to_pdf.py input.py output.pdf "relative/path.py"

# Or via bash wrapper
./scripts/print_single_file_to_pdf.sh path/to/file.py $(pwd)
```

### Testing directory conversion

```bash
./scripts/print_all.sh \
  path/to/directory \
  config/vimrc \
  '["node_modules", ".git"]' \
  'env*' \
  '["js", "py", "ts"]' \
  '["README"]' \
  'true' \
  '' \
  '' \
  '' \
  ''
```

### Testing Chinese character support

```bash
# Create test file with Chinese
cat > /tmp/test_chinese.py << 'EOF'
# 测试中文注释
def hello():
    print("你好，世界！")  # Hello World
EOF

# Convert to PDF
./bin/code2pdf --dev -s /tmp/test_chinese.py
```

### Installing CJK fonts (for Chinese/Japanese/Korean support)

```bash
# Quick installation for Simplified Chinese
./scripts/setup_cjk_fonts.sh sc

# For other languages
./scripts/setup_cjk_fonts.sh tc   # Traditional Chinese
./scripts/setup_cjk_fonts.sh jp   # Japanese
./scripts/setup_cjk_fonts.sh kr   # Korean
./scripts/setup_cjk_fonts.sh all  # All CJK languages

# See full guide
cat docs/font_installation_guide.md
```

### Checking dependencies

```bash
command -v python3 && command -v gs && command -v jq
python3 -c "import pygments; import weasyprint" && echo "Python packages OK"
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

## File Processing Logic

### code2pdf Default Filtering Rules
- **Blacklisted folders**: `node_modules`, `.git`, `dist`, `out`
- **Blacklisted patterns**: `env*`
- **Whitelisted extensions**: `rb`, `sh`, `md`, `js`, `py`, `ts`, `java`, `cpp`, `h`, `c`, `html`
- **Whitelisted filenames**: `README`, `LICENSE`, `Makefile`, `launch.json`
- **Include files without extensions**: `true` (for Dockerfile, etc.)
- **Additional parameters**: `--ignore-files`, `--ignore-types`, `--ignore-folders`, `--include-types`

### code2txt Default Filtering Rules
- **Ignored extensions**: `bin`, `pdf`, `jpg`, `png`, `gif`, `zip`, `tar`, `gz`, `exe`, `dll`, `so`, `dylib`, `class`, `jar`, `war`, `ear`, `pyc`, `pyo`, `txt`
- **Ignored folders**: `node_modules`, `.git`, `dist`, `out`, `build`, `__pycache__`, `.venv`, `venv`, `env`, `.env`, `vendor`, `target`
- **Max file size**: `500K` (configurable)
- **Include-types**: When specified, overrides ignore-types and only processes specified extensions

### code2pdf Processing Flow
1. Create a private per-run work directory (`mktemp -d`), removed on exit
2. Recursively traverse directories applying filtering rules
3. Convert each qualifying file to PDF using Python script
4. Generate table of contents from processed files
5. Merge all PDFs including table of contents into `merged.pdf`

### code2txt Processing Flow
1. Parse command-line arguments and validate input directory
2. Recursively traverse directories with symbolic link protection
3. Apply filtering rules (ignore/include types, folders, file size)
4. Detect language for each file for syntax highlighting
5. Generate optional table of contents
6. Combine files with markdown formatting into output file

## Important Implementation Details

### code2pdf
- Uses Python/Pygments for syntax highlighting with full UTF-8 support
- File path transformations use Perl regex: `/` → `____`, `.` → `----`
- Symbolic link recursion is prevented by tracking visited real paths
- All intermediate files are stored in a private `mktemp -d` work directory before final merge; other files in `/tmp` are never touched
- Error handling includes explicit checks for PDF creation and file moves
- Debug output is sent to stderr to avoid interfering with normal operation
- Filtering logic now matches code2txt for consistency

### code2txt
- Language detection maps file extensions to markdown language identifiers
- Cross-platform file size checking using different stat commands for macOS/Linux
- Files are sorted alphabetically for consistent output
- Table of contents is optional and placed at the beginning
- Output uses markdown code blocks with proper syntax highlighting
- Default ignores `.txt` files to prevent recursive inclusion of output file

## Common Issues

**DEV_MODE path**: The `--dev` flag uses a hardcoded macOS path (`/Users/huangweijing/git/code2pdf`). Update `bin/code2pdf:8` when testing locally.

**Whitespace in paths**: All scripts properly quote variables to handle spaces in file/folder names.

**Temporary files**: `print_all.sh` writes intermediate PDFs to its own `mktemp -d` directory (under `$TMPDIR`) and deletes it on exit, so concurrent runs and unrelated PDFs in `/tmp` are safe.

**Output location**:
- Single file: PDF goes to current working directory
- All files: `merged.pdf` goes to the root directory argument passed to the script

**Chinese/CJK character issues**:
- Ensure Noto Sans CJK fonts are installed in `~/.local/share/fonts/noto-cjk/`
- Run `fc-cache -f ~/.local/share/fonts/` to rebuild font cache
- Check font availability: `fc-list | grep -i "noto.*cjk"`

**Python dependency issues**:
- Install Pygments: `pip3 install --user pygments`
- Install WeasyPrint: `pip3 install --user weasyprint`
- WeasyPrint requires system libraries (see docs/font_installation_guide.md)

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

## File Structure

```
bin/
  code2pdf                      # Main PDF CLI entry point
  code2txt                      # Main text CLI entry point
scripts/
  code_to_pdf.py                # Python script: source code → PDF (UTF-8 support)
  print_single_file_to_pdf.sh   # Bash wrapper for single file PDF
  print_all.sh                  # Recursive directory PDF converter
  combine_to_txt.sh             # Text combination script
  setup_cjk_fonts.sh            # CJK font installation script
config/
  vimrc                         # Legacy Vim config (no longer used)
  colors/
    print_bw.vim                # Black & white color scheme
tests/                          # Automated test suite
docs/                           # Documentation
  font_installation_guide.md    # CJK font installation guide
```

## Migration from Vim to Python/Pygments

**Why the change?**
- Vim's `:hardcopy` has poor UTF-8/CJK support (uses legacy GB2312 charset)
- Limited to PostScript fonts that don't include Chinese characters
- Modern Python stack (Pygments + WeasyPrint) provides:
  - Full UTF-8 support
  - 500+ language syntax highlighting
  - Better font handling with TrueType/OpenType fonts
  - Active maintenance and updates

**What was replaced?**
- Old: Vim → PostScript → ps2pdf
- New: Pygments → HTML → WeasyPrint → PDF
- PDF merging still uses Ghostscript (unchanged)
