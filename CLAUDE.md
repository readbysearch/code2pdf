# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains two command-line tools:
- **code2pdf**: Converts source code files to PDF format with syntax highlighting and table of contents. Uses Python/Pygments for syntax highlighting with full UTF-8 and CJK support, and WeasyPrint to render a whole directory as one PDF in a single pass.
- **code2txt**: Combines source code files into a single markdown-formatted text file optimized for LLM context input, with table of contents and syntax highlighting.

## Architecture

The project consists of:

### Entry Points
- **`bin/code2pdf`** - PDF conversion tool with dependency checking and routing
- **`bin/code2txt`** - Text combination tool with flexible filtering options

### Processing Scripts
- **`scripts/code_to_pdf.py`** - Single-file mode (same design, no contents page) and shared helpers (`lexer_for`, `read_source`)
- **`scripts/theme.py`** - Themes (paper, mono, any Pygments style), bundled font setup and page CSS
- **`scripts/progress.py`** - Page estimate and progress display ([1/3] preparing, [2/3] layout per page, [3/3] writing)
- **`scripts/parts.py`** - Big documents (> 2 × 100 estimated pages): render ~100-page parts in child processes, then join with pypdf
- **`fonts/`** - Bundled IBM Plex Mono/Sans TTFs (OFL 1.1); found relative to `scripts/` in every install layout
- **`scripts/print_single_file_to_pdf.sh`** - Converts individual files to PDF using Python script
- **`scripts/print_all.sh`** - Thin wrapper: validates the directory and runs `dir_to_pdf.py`
- **`scripts/dir_to_pdf.py`** - Selects files and renders the table of contents plus all files as one PDF
- **`scripts/combine_to_txt.sh`** - Combines files into markdown-formatted text

### Configuration
- **`config/vimrc`** - Legacy Vim configuration (no longer used for PDF generation)

## Key Components

### code2pdf (`bin/code2pdf`)
- Finds its install directory from its own real location (following symlinks), or `$CODE2PDF_HOME` if set (the Homebrew formula sets it); errors out if `scripts/` is missing there
- Puts a private Python environment first on PATH when present: `venv/` (created by `install.sh`) or `.venv/` (a checkout)
- `--help` and usage errors are handled before dependency checks; `--dev` is accepted but does nothing (kept for compatibility)
- Performs dependency checking for `python3`, `pygments` and `weasyprint`
- Routes to appropriate processing script based on `-s` (single file) or `-a` (all files) options
- Defines default filtering rules for directory processing

### Design (`scripts/theme.py`, `scripts/dir_to_pdf.py`)
- Source code → HTML (Pygments) → PDF (WeasyPrint); both modes share `dir_to_pdf.render_document`
- Themes: `paper` (default, print-designed colours that also differ in lightness/weight/slant), `mono` (black & white), or any Pygments style (code colours only; dark styles get a dark code block on the white page). Chosen with `--theme` or `$CODE2PDF_THEME`
- Fonts: bundled IBM Plex Mono (code, true italics for comments) and Plex Sans (titles, contents, page headers) via `@font-face`; CJK falls back to PingFang/Hiragino/Noto CJK
- Language: by file name, else by a `#!` line (`lexer_for(path, source)`), else plain text
- Layout: line numbers in the left margin (`::before` counters on Pygments `linespans`), wrapped lines hang under the code; each file opens with folder, name and details; page header = path (left) and `project, date` (right)
- Dates (`source_info`): contents page shows `Printed <date> from commit <hash> (<branch>)` (+ `with uncommitted changes`); each file shows `last changed <date>` (one streamed `git log --relative`), `uncommitted changes` (from `git status`), or `modified <date>` outside git. `$SOURCE_DATE_EPOCH` fixes the printing date; PDF metadata gets title and creation time
- Progress: `render_document` forwards WeasyPrint's `weasyprint.progress` log (Step 1 / per-page Step 5 / Step 6) to `progress.Progress`; `estimate_pages` predicts the total from rows (wrapped at 89 columns, 59 rows per page), exact on ClaudeTerminal (873 pages). In a terminal a ticker thread keeps the two silent stages moving; `-q`/`--quiet`/`$CODE2PDF_QUIET` turns it off. Measured on ClaudeTerminal (189 files, 41k lines): 0:13 preparing, 0:27 layout, 0:18 writing, ~4.5 GB peak memory
- Parts mode (`parts.py`): WeasyPrint keeps all pages in memory until writing (~0.6 GB + ~6.5 MB/page), so documents over `2 × $CODE2PDF_PART_PAGES` (default 100) estimated pages are split into parts of whole files, each rendered by `render_part` in a spawned child (headers/footers off, contents page off). The parent then renders the contents page with written-in numbers (`build_contents(page_numbers=...)`, links `code2pdf:f<i>`), renders an overlay of empty pages carrying headers/footers (`theme.overlay_css`), and joins with pypdf: `add_page` (not `append`, which imports one named destination per code line: 10× slower, 6× bigger), `merge_page` + `compress_content_streams`, link rewiring to `/Dest`, outline, metadata. `-j/--jobs`/`$CODE2PDF_JOBS` (default 3 with ≥16 GB RAM, 2 with ≥8 GB, else 1; capped at CPU count). Verified on ClaudeTerminal: all 563 pages text-identical and pixel-identical to single pass (sampled incl. part boundaries), same 294 contents link rects/targets and 116 bookmarks; differences: no per-line named destinations, ~25% larger file. ClaudeTerminal 563 pages: 1 job 52 s/1.9 GB, 2 jobs 30 s/3.1 GB, 3 jobs 23 s/3.7 GB; single pass 54 s/4.2 GB. `$CODE2PDF_DEBUG_TIMING` prints per-stage timings
- One block per code line costs ~60% more render time than the v3.3 markup (7.8 s vs 4.9 s for this repo); it is what makes wrapped lines hang cleanly

### code2txt (`bin/code2txt`)
- Parses command-line arguments for flexible configuration
- Validates input directories and converts to absolute paths
- Supports file filtering (ignore-types, include-types, ignore-folders, ignore-files)
- Configurable file size limits with human-readable formats (K, M, G)
- Optional table of contents generation
- Verbose mode for debugging

### PDF Directory Processing (`scripts/print_all.sh` → `scripts/dir_to_pdf.py`)
- `print_all.sh` keeps the original 11 positional arguments and `exec`s `dir_to_pdf.py`
- JSON lists for blacklisted folders, whitelisted extensions and special file names; plus ignore-files, ignore-types, ignore-folders, include-types
- Selection rules are identical to the old bash implementation (covered by `tests/test_dir_to_pdf.py`); hidden entries are skipped, symlink loops are cut by tracking real paths, and the output file is never included
- Files are ordered depth-first, sorted by name within each folder
- Builds one HTML document — table of contents, then one `<section>` per file — and renders it with WeasyPrint once (about 4× faster than the old per-file PDFs + Ghostscript merge)
- The table of contents uses `target-counter()` for real page numbers and links; file headings become PDF bookmarks and the page header (`string-set`)
- `--list-files` prints the selection without rendering (useful for debugging filters)
- Writes to a temp file next to `merged.pdf` and renames it into place

### Text Combination (`scripts/combine_to_txt.sh`)
- Directory traversal with symbolic link protection
- Language detection for markdown syntax highlighting
- Cross-platform file size checking (macOS/Linux)
- Sorted file output for consistent results
- Markdown formatting with code blocks
- Handles files without extensions (Dockerfile, Makefile, etc.)

### Single File PDF Processing (`scripts/print_single_file_to_pdf.sh`)
- Calls `code_to_pdf.py`, which renders the file with the same design (no contents page)
- Output goes to current working directory

## Key Technical Details

**Dependencies** (Ghostscript and jq are no longer needed):
- Python 3 with packages: pygments (syntax highlighting), weasyprint (HTML→PDF), pypdf (joining parts)

**Font Support**:
- Latin text uses the bundled IBM Plex fonts; Chinese/Japanese/Korean comes from system fonts
- macOS: no setup needed; Pango falls back to system CJK fonts (PingFang, Hiragino, Apple SD Gothic/Nanum)
- Linux: install `fonts-noto-cjk`, or run `setup_cjk_fonts.sh` (installs to `~/.local/share/fonts/noto-cjk/`)
- **Installation guide**: See `docs/font_installation_guide.md`
- **Quick setup**: Run `./scripts/setup_cjk_fonts.sh [sc|tc|jp|kr|all]`

**Migration from Vim to Python/Pygments**:
- Old approach used Vim hardcopy with PostScript (poor UTF-8/CJK support)
- New approach uses Python/Pygments for better UTF-8 support and 500+ languages
- `config/vimrc` retained for reference only

## Development Commands

### Testing code2pdf

Run the launcher straight from the checkout; it uses this checkout's `scripts/` and `.venv/` (create it with `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`):

```bash
./bin/code2pdf -s path/to/file.py
./bin/code2pdf -a path/to/directory
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
./bin/code2pdf -s /tmp/test_chinese.py
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
command -v python3
python3 -c "import pygments; import weasyprint" && echo "Python packages OK"
```

### Running Automated Tests

```bash
# Set up test environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-test.txt

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

## Installation and Releases

- **Users**: `brew install readbysearch/tap/code2pdf` (formula in [readbysearch/homebrew-tap](https://github.com/readbysearch/homebrew-tap)), or `install.sh` on Linux without Homebrew.
- **Canonical repository**: `readbysearch/code2pdf` (the old `waleking/code2pdf` fork is archived).
- **Ubuntu/Debian**: `packaging/deb/build-deb.sh VERSION [DIR]` builds `code2pdf_VERSION_all.deb` (files in `/usr/share/code2pdf`, symlinks in `/usr/bin`, man pages from `packaging/deb/man/`); it depends on Ubuntu's `weasyprint (>= 61)`, `python3-pygments`, recommends `python3-pypdf`, `fonts-noto-cjk`. `packaging/deb/test-deb.sh DEB` installs/uses/removes it in a fresh container. `.github/workflows/release-deb.yml` runs on every `v*` tag: build + `lintian --fail-on warning`, unit tests and install test on Ubuntu 24.04 and 26.04 containers, then attaches `code2pdf_X_all.deb` and `code2pdf_all.deb` (stable `releases/latest/download/` name) to the GitHub release
- **No-sudo installs** (`install.sh --user`): system `python3 -m venv` if `ensurepip` exists, else `venv --without-pip` + `get-pip.py`; if WeasyPrint still can't load (no Pango) or there is no python3, download micromamba (`mamba-org/micromamba-releases`) and create `venv/` from conda-forge (`python pygments weasyprint pypdf`, ~400 MB); `--conda` forces it. The launcher just uses `venv/bin/python3`. Tested as a non-root user on Ubuntu 24.04 with: no python3-venv (~100 MB), no Pango (conda), no Python (conda), everything
- **Compatibility notes** (found on Ubuntu): WeasyPrint < 62 ignores `calc()` in the code-line indent (use plain lengths); minimal Ubuntu has no `rev` or `file`; pypdf is optional (22.04 has none: big documents fall back to one pass)
- **Release**: commit and push to `main`, push an annotated tag `vX.Y.Z` (this also builds and attaches the `.deb`), then in `homebrew-tap` update the formula's `url` and `sha256` (`curl -sL https://github.com/readbysearch/code2pdf/archive/refs/tags/vX.Y.Z.tar.gz | shasum -a 256`), run `brew audit --strict --online readbysearch/tap/code2pdf`, and push. Details: `what_to_do_after_update_for_developer.md` in the tap repo.
- The formula installs Pygments + WeasyPrint into its own virtualenv and sets `CODE2PDF_HOME`, so the scripts' plain `python3` must stay compatible with that.

## File Processing Logic

### code2pdf Default Filtering Rules
- **Blacklisted folders**: `node_modules`, `.git`, `dist`, `out`, `build`, `target`, `DerivedData`, `Pods`, `vendor`, `__pycache__`, `venv` (hidden folders are always skipped)
- **Blacklisted patterns**: `env*`
- **Whitelisted extensions**: C family (`c h cc cpp cxx hh hpp m mm`), `swift go rs zig`, JVM (`java kt kts scala groovy gradle`), `cs fs`, scripting (`py rb php pl lua r jl dart ex exs erl hs ml clj`), web (`js mjs cjs jsx ts tsx vue svelte html css scss`), `sql proto graphql`, shells (`sh bash zsh fish ps1`), docs/config (`md rst yaml yml toml`). JSON is left out on purpose (lockfiles).
- **Whitelisted filenames**: `README`, `LICENSE`, `Makefile`, `launch.json`
- **Include files without extensions**: `true` (for Dockerfile, etc.)
- **Additional parameters**: `--ignore-files`, `--ignore-types`, `--ignore-folders`, `--include-types`; `--list-files` shows the selection without converting
- Defaults live in `bin/code2pdf` (`DEFAULT_*`); tests: `test_default_selection_covers_common_languages_and_skips_build_output`

### code2txt Default Filtering Rules
- **Ignored extensions**: `bin`, `pdf`, `jpg`, `png`, `gif`, `zip`, `tar`, `gz`, `exe`, `dll`, `so`, `dylib`, `class`, `jar`, `war`, `ear`, `pyc`, `pyo`, `txt`
- **Ignored folders**: `node_modules`, `.git`, `dist`, `out`, `build`, `__pycache__`, `.venv`, `venv`, `env`, `.env`, `vendor`, `target`
- **Max file size**: `500K` (configurable)
- **Include-types**: When specified, overrides ignore-types and only processes specified extensions

### code2pdf Processing Flow
1. Recursively traverse directories applying filtering rules
2. Highlight every selected file with Pygments into one HTML document, table of contents first
3. Render that document once with WeasyPrint into `merged.pdf` (fails with "no matching files" if nothing was selected)

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
- Symbolic link recursion is prevented by tracking visited real paths
- No intermediate per-file PDFs and no `/tmp` work files; only a temp file next to the output, renamed into place
- Page headers show paths relative to the converted directory
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

**Which copy runs**: `bin/code2pdf` always uses the `scripts/` next to its real location, so `./bin/code2pdf` tests your working tree, while `code2pdf` on PATH runs the installed copy (Homebrew: `$(brew --prefix)/opt/code2pdf`).

**code2txt output file**: the output file is skipped by real path, so writing it inside the scanned directory is safe.

**Whitespace in paths**: All scripts properly quote variables to handle spaces in file/folder names.

**Temporary files**: directory conversion writes only `.code2pdf-*.pdf` next to `merged.pdf` while rendering, then renames it; nothing in `/tmp` is touched.

**Output location**:
- Single file: PDF goes to current working directory
- All files: `merged.pdf` goes to the root directory argument passed to the script

**Chinese/CJK character issues**:
- Ensure Noto Sans CJK fonts are installed in `~/.local/share/fonts/noto-cjk/`
- Run `fc-cache -f ~/.local/share/fonts/` to rebuild font cache
- Check font availability: `fc-list | grep -i "noto.*cjk"`

**Python dependency issues**:
- Homebrew install: `brew reinstall readbysearch/tap/code2pdf` (bundles both packages)
- Checkout: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` (Homebrew's Python rejects `pip install --user`)
- WeasyPrint needs Pango: `brew install pango` / `apt install libpango-1.0-0 libpangoft2-1.0-0`

## Testing

### Test Suite Overview
- **101 automated tests** covering both tools
- **Test framework**: pytest with subprocess-based testing
- **Test coverage**:
  - code2txt: 16 unit tests (`test_code2txt.py`) + 1 output-file regression test (`test_code2txt_output.py`)
  - code2pdf: 10 unit tests (`test_code2pdf.py`)
  - Launchers: 10 tests (`test_launcher.py`): symlinks, `CODE2PDF_HOME`, help without dependencies, `--theme`, `--list-themes`, default selection, `--jobs`
  - Parts: 15 tests (`test_parts.py`): partitioning, joined output text-identical to single pass, contents links and bookmarks, headers/footers on every page, metadata, no leftovers
  - Directory conversion: 4 tests (`test_print_all_tmp.py`): `/tmp` isolation, missing directory
  - One-pass renderer: 12 tests (`test_dir_to_pdf.py`): filter parity with the old bash rules, table of contents first with correct page numbers, relative headers, no Ghostscript needed
  - Design: 17 tests (`test_design.py`): themes, embedded Plex fonts, `#!` language detection, git/mtime dates, printing date, grouped contents page, single-file design
  - Progress: 8 tests (`test_progress.py`): page estimate, terminal vs log output, ticking silent stages, time left, quiet
  - Integration: 8 tests (`test_integration.py`)
- code2pdf tests need Pygments and WeasyPrint in `.venv/` (see Running Automated Tests); they skip or fail without them
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
install.sh                      # Installer for Linux without Homebrew (private venv + symlinks)
packaging/deb/                  # build-deb.sh, test-deb.sh, man pages for the Ubuntu/Debian package
.github/workflows/release-deb.yml  # Builds, tests and attaches the .deb on every v* tag
requirements.txt                # Runtime Python packages (pygments, weasyprint)
requirements-test.txt           # Test dependencies
scripts/
  code_to_pdf.py                # Python script: source code → PDF (UTF-8 support)
  print_single_file_to_pdf.sh   # Bash wrapper for single file PDF
  print_all.sh                  # Directory conversion entry point (wraps dir_to_pdf.py)
  theme.py                      # Themes, bundled fonts, page CSS
  progress.py                   # Page estimate and progress display
  parts.py                      # Render big documents in parts and join them
  dir_to_pdf.py                 # One-pass directory → PDF renderer with table of contents
  combine_to_txt.sh             # Text combination script
  setup_cjk_fonts.sh            # CJK font installation script
fonts/                          # IBM Plex Mono/Sans TTFs + LICENSE-IBM-Plex.txt (OFL 1.1)
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
- Directory mode no longer merges per-file PDFs with Ghostscript; everything is rendered in one WeasyPrint pass
