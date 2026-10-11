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

- **test_code2pdf.py**: code2pdf command line basics
  - `--help`, unknown options, no arguments
  - Missing file / missing directory errors
  - `--dev` is still accepted (no-op)

- **test_code2txt_output.py**: code2txt never reads its own output file

- **test_code2txt_files_from.py**: code2txt `--files-from`: the listed files in order, binary
  files skipped with one line, missing and outside files are errors

- **test_launcher.py**: Launcher behaviour
  - Works through symlinks (as created by `install.sh` or `ln -s`)
  - `CODE2PDF_HOME` override and missing-scripts error
  - `--help` works without PDF dependencies

- **test_dir_to_pdf.py**: One-pass directory renderer
  - File selection identical to the old bash rules (`--list-files`)
  - `--include`/`--exclude` globs (precedence, hidden and skipped folders, unused-glob warnings)
    and `--files-from` (given order, exclusions, binary files reported in one line)
  - Table of contents first, with page numbers that match where each file starts
  - Relative page headers, CJK, no Ghostscript needed, clear error when nothing matches

- **test_design.py**: PDF design
  - Themes: paper, mono and Pygments styles render; unknown names are rejected
  - Bundled IBM Plex fonts are embedded (no Courier/Verdana fallback)
  - Language detection from `#!` lines; dates from git, `uncommitted changes`, mtime outside git
  - Printing date (`SOURCE_DATE_EPOCH`), grouped contents page, single-file mode

- **test_progress.py**: Progress display
  - Page estimate (wrapped lines, one page per file, contents page)
  - One updating line in a terminal, a line per 10% in logs, `--quiet`
  - Elapsed time keeps ticking while WeasyPrint prepares and writes; time left includes writing

- **test_parts.py**: Big documents rendered in parts (forced small with `CODE2PDF_PART_PAGES`)
  - Joined output has the same text on every page as a single pass
  - Contents links and bookmarks point at each file; headers/footers on every page; metadata

- **test_install_sh.py**: install.sh PATH setup (leaves a stock Ubuntu `~/.profile` alone) and latest-release selection, by sourcing the script

- **test_version.py**: `--version`: version from VERSION/git, install kind, library versions, works without WeasyPrint

- **test_cjk_fonts.py**: Warning when no installed font covers Chinese/Japanese/Korean text (fake `fc-list`)

- **test_print_all_tmp.py**: Directory conversion safety
  - Leaves unrelated files in `/tmp` alone; the PDF contains only its own pages
  - Leaves no work files behind
  - Fails fast on a missing directory

- **test_line_ranges.py**: Part of a file (`path:START-END`) in code2pdf, `-s` and code2txt
  - Parsing, merging and clamping ranges; errors name the file; a file named like a range stays whole
  - Real line numbers and "not shown" markers in the PDF, the same in parts mode
  - The warning when a range stops inside a block; `-s` with an absolute path

- **test_changes.py**: Marks and `--changed`
  - `path:+START-END` and `path:-N` (print and mark, lines removed), list round trips
  - `--changed REV`: pieces grown to small blocks, header lines, context up to a blank line;
    deleted, renamed, untracked and binary files; subfolders, `--exclude`, error messages
  - The list fed to `--files-from` and code2txt; parts mode prints the same marks
  - `--summary` under the title and as the PDF's Subject; no Subject without it

- **test_interrupt.py**: A killed conversion (SIGTERM to the launcher or its group, Ctrl-C)
  stops its workers and leaves no temp files, also under a non-reaping PID 1 as in CI

- **test_plugin.py**: The Claude Code plugin and marketplace manifests, the skill's front
  matter, and that every option the skill names exists in `--help`

- **test_integration.py**: Integration tests for both tools
  - Large repository simulation
  - Mixed content types
  - Unicode handling
  - Performance tests
  - Consistency checks

## Test Fixtures

The `fixtures/` directory contains sample files for testing:
- **sample_project/**: A complete project with multiple file types
- **edge_cases/**: A file with special characters in its content
- Empty directories and large files are created per test in a temporary directory (`empty_dir`, `create_large_file` in `conftest.py`)

## Notes

- code2pdf tests need Pygments and WeasyPrint (in `.venv/`), and `pdftotext`/`pdffonts`/`pdfinfo` (poppler) for text checks; some skip without them. Ghostscript is only used by the tests to count pages
- `bin/code2pdf` runs the scripts in this checkout, not an installed copy, so tests always exercise your working tree
- Tests are designed to work on both Linux and macOS
- The test suite uses subprocess to test the actual bash scripts