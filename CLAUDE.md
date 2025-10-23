# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

code2pdf is a Bash-based CLI tool that converts source code files to PDF format with syntax highlighting and a table of contents. It uses Pygments for syntax highlighting, WeasyPrint for HTML to PDF conversion, and Ghostscript for merging PDFs. **Full UTF-8 and CJK (Chinese/Japanese/Korean) support included.**

## Architecture

The tool has a four-tier architecture:

1. **Main entry point** (`bin/code2pdf`): Command-line parser and dispatcher
   - Handles `--dev` mode for development (hardcoded to macOS path)
   - Checks dependencies (python3, pygments, weasyprint, gs, jq)
   - Routes to either single-file or all-files script
   - Defines default blacklists, whitelists, and file filters

2. **Python PDF generator** (`scripts/code_to_pdf.py`): Core conversion logic
   - Converts source code → HTML (with Pygments) → PDF (with WeasyPrint)
   - Full UTF-8 and CJK character support
   - Syntax highlighting for 500+ languages
   - Configurable fonts with fallback support
   - Generates headers with file paths and page numbers

3. **Single file converter** (`scripts/print_single_file_to_pdf.sh`):
   - Wrapper script that calls Python PDF generator
   - Output goes to current working directory

4. **Directory converter** (`scripts/print_all.sh`):
   - Recursively processes directories with symbolic link detection
   - Step 1: Convert all matching files to PDF in `/tmp/` using Python script
   - Step 2: Generate table of contents from processed files
   - Step 3: Merge all PDFs (including TOC) into `merged.pdf` in root directory
   - File naming: transforms paths like `src/file.js` → `src____file----js.pdf` to avoid conflicts

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

**Legacy Vim Configuration** (no longer used for PDF generation):
- Old approach used Vim hardcopy with PostScript
- Replaced with Python/Pygments for better UTF-8 support
- `config/vimrc` retained for reference

**File filtering** (in `print_all.sh`):
- Blacklisted folders: `node_modules`, `.git`, `dist`, `out`
- Blacklisted pattern: `env*`
- Whitelisted extensions: `rb`, `sh`, `md`, `js`, `py`, `ts`, `java`, `cpp`, `h`, `c`, `html`
- Whitelisted files: `README`, `LICENSE`, `Makefile`, `launch.json`
- Files without extensions included by default (e.g., Dockerfile)

**Symbolic link handling**: `print_all.sh` maintains a `visited_dirs` array to prevent infinite recursion when following symbolic links.

## Development Commands

### Running the tool in development mode

To test changes without installing via Homebrew, use `--dev` flag (requires updating hardcoded path in `bin/code2pdf:8` to your local path):

```bash
./bin/code2pdf --dev -s path/to/file.py
./bin/code2pdf --dev -a path/to/directory
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
  'true'
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

### Checking dependencies

```bash
command -v python3 && command -v gs && command -v jq
python3 -c "import pygments; import weasyprint" && echo "Python packages OK"
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

## Common Issues

**DEV_MODE path**: The `--dev` flag uses a hardcoded macOS path (`/Users/<you>/git/code2pdf`). Update `bin/code2pdf:8` when testing locally.

**Whitespace in paths**: All scripts properly quote variables to handle spaces in file/folder names.

**Temporary files**: Scripts use `/tmp/` for intermediate PDF files. `print_all.sh` cleans up at the start.

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
- WeasyPrint requires system libraries (installed via ps2pdf guide)

## File Structure

```
bin/code2pdf                      # Main CLI entry point
scripts/
  code_to_pdf.py                  # Python script: source code → PDF (UTF-8 support)
  print_single_file_to_pdf.sh     # Bash wrapper for single file
  print_all.sh                    # Recursive directory converter
config/
  vimrc                           # Legacy Vim config (no longer used)
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
