# code2pdf

Convert source code files to PDF or combine them into a single text file, with table of contents and syntax highlighting, optimized for sharing, printing, or LLM context input.

## Features

### code2pdf
- Convert single source code files to PDF
- Convert entire directories of code files to PDF with a table of contents
- Preserve syntax highlighting and formatting
- Support for 500+ programming languages (via Pygments), detected from the file name or a `#!` line
- **Full UTF-8 and CJK support** (Chinese, Japanese, Korean)
- Designed for print: bundled IBM Plex fonts, a colour theme that stays readable in black and white, a black & white theme, or any Pygments theme
- Dates that identify the printout: printing date and git commit on the contents page, last change per file
- Available as a command-line tool

### code2txt
- Combine source code files into a single text file
- Generate markdown-formatted output optimized for LLM context
- Configurable file filtering and size limits
- Automatic language detection for syntax highlighting
- Table of contents generation

## Installation

### Homebrew (macOS and Linux — recommended)

```bash
brew install readbysearch/tap/code2pdf
```

Installs both `code2pdf` and `code2txt` with everything they need (Python, Pygments,
WeasyPrint, Pango) in a private environment — no `pip install` required.

### Install script (Linux without Homebrew)

Install the system packages first, then run the script:

```bash
# Ubuntu/Debian
sudo apt install curl python3-venv libpango-1.0-0 libpangoft2-1.0-0 fonts-noto-cjk
# Fedora/RHEL
sudo dnf install curl python3 pango google-noto-sans-cjk-fonts

# Install for current user (~/.local, no sudo)
curl -sSL https://raw.githubusercontent.com/readbysearch/code2pdf/main/install.sh | bash -s -- --user

# Or system-wide (/usr/local, requires sudo)
curl -sSL https://raw.githubusercontent.com/readbysearch/code2pdf/main/install.sh | bash -s -- --system
```

The script copies the tools to `~/.local/share/code2pdf` (or `/usr/local/share/code2pdf`),
creates a private Python environment there with Pygments and WeasyPrint, links the commands
into `~/.local/bin` (or `/usr/local/bin`), and verifies the install by converting a test file.
Re-run it to upgrade; `--ref v3.3` installs a specific release.

### From a checkout (development)

```bash
git clone https://github.com/readbysearch/code2pdf.git
cd code2pdf
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # pygments, weasyprint, pypdf
# WeasyPrint also needs Pango (brew install pango / apt install libpango-1.0-0 libpangoft2-1.0-0)

./bin/code2pdf -s myfile.py   # uses ./scripts and ./.venv automatically
```

The launchers find their scripts relative to their own location (following symlinks),
so you can also link them onto your PATH:

```bash
ln -s "$(pwd)/bin/code2pdf" ~/.local/bin/code2pdf
ln -s "$(pwd)/bin/code2txt" ~/.local/bin/code2txt
```

## Usage

### code2pdf - Convert to PDF

Convert a single file:
```bash
code2pdf -s myfile.py
```

Convert all files in a directory:
```bash
code2pdf -a src/
```

Choose a theme:
```bash
code2pdf -a src/                          # paper (default): colour, designed for print
code2pdf -a src/ --theme mono             # black & white, for laser printers
code2pdf -a src/ --theme solarized-light  # any Pygments theme for the code
code2pdf --list-themes                    # every theme name
```

See which files `-a` would include, without converting:
```bash
code2pdf -a . --list-files
```

By default `-a` includes source files of common languages (C/C++/Objective-C, Swift, Go, Rust,
Java/Kotlin, C#, Python, Ruby, JavaScript/TypeScript, shell, SQL, …), Markdown, YAML and TOML,
plus `README`, `LICENSE`, `Makefile` and files without an extension such as `Dockerfile`. It skips
hidden folders, `node_modules`, `build`, `dist`, `out`, `target`, `DerivedData`, `Pods`, `vendor`,
`__pycache__`, `venv` and `env*`. Adjust with `--include-types`, `--ignore-types`,
`--ignore-folders` and `--ignore-files`.

Show help:
```bash
code2pdf --help
```

Output: `-s` writes `<name>.pdf` to the current directory; `-a` writes `merged.pdf`
into the directory you converted. The whole directory is rendered in one pass:

- **Contents page**: files grouped by folder with page numbers (clickable), the number of
  files and lines, and when it was printed, e.g. `Printed 2026-10-09 from commit 7afaa74 (main)`
  (`with uncommitted changes` if any file has local edits).
- **Each file** starts on a new page with its folder, name, and details such as
  `Python, 241 lines, last changed 2026-10-08` (from git; `uncommitted changes` for local edits;
  `modified <date>` outside a git repository). Each file is also a PDF bookmark.
- **Every page** shows the file path, the project name with the printing date, and the page number.

Set `SOURCE_DATE_EPOCH` to fix the printing date for reproducible output.

Large directories show their progress while converting (`-q` / `--quiet` turns it off):

```
code2pdf: 189 files, 41,005 lines (~873 pages)
  [2/3] Laying out page 366 of ~873  [████████░░░░░░░░░░░░]  41%  0:25 elapsed, ~0:32 left
Done: 873 pages in 0:59 → /path/to/project/merged.pdf
```

The page count is estimated up front from line counts and line lengths. In a terminal the
status updates in place; in logs or pipes a line is printed every 10%.

**Big directories** (more than ~200 pages) are rendered in parts of ~100 pages, each in its own
process, then joined, so memory stays bounded (about 1.3 GB per part) and several CPU cores are
used. `-j N` / `--jobs N` sets how many parts render at once (default 3 with 16 GB of RAM or
more, 2 with 8 GB, else 1). A 563-page project takes ~23 s with 3 parts at a time (3.7 GB peak), ~30 s
with 2 (3.1 GB), and ~52 s with 1 (1.9 GB); without parts it took 54 s and 4.2 GB.
The joined PDF looks the same as a single-pass one (same text, pixels, contents links
and bookmarks); it is ~25% bigger because each part embeds its own font subset.

## Fonts

code2pdf bundles [IBM Plex](https://github.com/IBM/plex) Mono and Sans (in `fonts/`, SIL Open Font
License 1.1), so PDFs look the same on every machine. Plex has no Chinese, Japanese or Korean
glyphs; those come from the system fonts.

### CJK Font Support

Chinese, Japanese and Korean text works out of the box on **macOS** — the system fonts
(PingFang, Hiragino, Apple SD Gothic/Nanum) are used automatically.

On **Linux**, install CJK fonts if your code contains them: `sudo apt install fonts-noto-cjk`
(Debian/Ubuntu), or use the bundled script for a per-user install:

```bash
./scripts/setup_cjk_fonts.sh sc   # sc, tc, jp, kr, or all (~150 MB)
```

**Full documentation**: [docs/font_installation_guide.md](docs/font_installation_guide.md)

### code2txt - Combine to Text File

Process current directory with default settings:
```bash
code2txt
```

Process specific directory with custom output:
```bash
code2txt -o output.txt src/
```

Include only specific file types:
```bash
code2txt --include-types js,ts,jsx,tsx src/
```

Exclude additional folders:
```bash
code2txt --ignore-folders test,docs src/
```

Skip large files:
```bash
code2txt --max-file-size 100K src/
```

Generate without table of contents:
```bash
code2txt --no-toc src/
```

Show verbose output:
```bash
code2txt --verbose src/
```

Show all options:
```bash
code2txt --help
```

#### code2txt Options

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --output` | Output filename | `combined.txt` |
| `--ignore-types` | File extensions to ignore | `bin,pdf,jpg,png,gif,zip,tar,gz,exe,dll,so,dylib,class,jar,war,ear,pyc,pyo,txt` |
| `--ignore-folders` | Folders to skip | `node_modules,.git,dist,out,build,__pycache__,.venv,venv,env,.env,vendor,target` |
| `--include-types` | Only include these file types (overrides ignore-types) | - |
| `--max-file-size` | Skip files larger than this (e.g., 500K, 1M) | `500K` |
| `--no-toc` | Skip table of contents generation | false |
| `--verbose` | Show processing details | false |

## Testing

The project includes a comprehensive test suite using pytest. Tests cover both code2pdf and code2txt functionality.

### Running Tests

1. Set up test environment (the code2pdf tests need the runtime packages too):
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-test.txt
```

2. Run tests:
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_code2txt.py

# Run with verbose output
pytest -v
```

See `tests/README.md` for detailed testing documentation.

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).

- For commercial use, please [open a GitHub issue](https://github.com/readbysearch/code2pdf/issues) to discuss licensing options
- For non-commercial use, you must comply with AGPL-3.0 terms

The bundled IBM Plex fonts in `fonts/` are licensed separately under the SIL Open Font License 1.1
(`fonts/LICENSE-IBM-Plex.txt`).