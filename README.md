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

### Ubuntu 24.04+ / Debian 13+ (.deb)

```bash
curl -LO https://github.com/readbysearch/code2pdf/releases/latest/download/code2pdf_all.deb
sudo apt install ./code2pdf_all.deb
```

`apt` installs the dependencies from Ubuntu itself (`weasyprint`, `python3-pygments`, and the
recommended `python3-pypdf` and `fonts-noto-cjk`), so they get Ubuntu's security updates. The
package is ~300 KB, works on any CPU, and includes `man code2pdf` / `man code2txt`. Remove it with
`sudo apt remove code2pdf`. Each release also has a versioned file, e.g. `code2pdf_3.6_all.deb`.

### Install script (other Linux without Homebrew)

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
creates a private Python environment there with Pygments, WeasyPrint and pypdf, links the
commands into `~/.local/bin` (or `/usr/local/bin`), and verifies the install by converting a
test file. It installs the **latest release**; `--ref v3.6` installs a specific one and `--ref main`
the newest, unreleased code. Re-run it to upgrade. It only adds `~/.local/bin` to your PATH if no
shell file does so already (Ubuntu's `~/.profile` does).

**No sudo?** `--user` needs no root at all. If `python3-venv` is missing it bootstraps pip
itself (~100 MB). If the Pango library or Python is missing, it downloads
[micromamba](https://mamba.readthedocs.io/) and builds the environment from conda-forge, which
brings its own Python, WeasyPrint and Pango (~400 MB); `--conda` forces this. If no
Chinese/Japanese/Korean font is installed, `--user` also installs Noto Sans Mono CJK into
`~/.local/share/fonts` (~26 MB) so CJK text doesn't print as empty boxes; `--no-cjk-fonts`
skips that.

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

#### Choosing files

By default `-a` includes source files of common languages (C/C++/Objective-C, Swift, Go, Rust,
Java/Kotlin, C#, Python, Ruby, JavaScript/TypeScript, shell, SQL, …), Markdown, YAML and TOML,
plus `README`, `LICENSE`, `Makefile` and files without an extension such as `Dockerfile` (not
JSON, `.txt` or other data files; add them with `--include`). It skips
hidden files and folders, binary files, `node_modules`, `build`, `dist`, `out`, `target`,
`DerivedData`, `Pods`, `vendor`, `__pycache__`, `venv` and `env*`.

```bash
code2pdf -a . --list-files                         # see what would be included, in order, without converting
code2pdf -a . --exclude tests --exclude '*.lock'   # leave out files and folders
code2pdf -a . --exclude src/legacy                 # only this folder, not lib/legacy
code2pdf -a . --include '*.json' --include .github # add what the defaults leave out
code2pdf -a . --include-types swift,m              # only these extensions
git ls-files src | code2pdf --files-from -         # exactly these files, in this order
printf 'src/app.py:120-180\nsrc/util.py\n' | code2pdf --files-from -   # part of a file, all of another
code2pdf -s src/app.py:120-180                     # part of one file
code2pdf -a src -o ~/Desktop/src.pdf               # choose where the PDF goes
```

| Option | Effect |
|--------|--------|
| `--exclude GLOB` | Leave out matching files and folders. Wins over everything else. |
| `--include GLOB` | Also include matching files of any type, even hidden ones or ones in skipped folders. A folder (`--include config`) brings every file in it. |
| `--files-from FILE` | Convert exactly the files listed in `FILE` (`-` for stdin), one per line, in that order: relative to the directory (default `.`) or absolute. Only `--exclude` and the binary check apply. `path:START-END` prints part of a file (see below). |
| `--include-types LIST` | Only these extensions (replaces the default list). |
| `--ignore-types LIST` | Skip these extensions. |
| `--ignore-folders LIST` | Skip folders with these names, at any depth. |
| `--ignore-files LIST` | Skip files with these names, at any depth. |
| `-o`, `--output PDF` | Write the PDF here (a folder: the default name inside it; missing folders are created). Works with `-s` too. |

Every option can be repeated (`--exclude a --exclude b`; lists add up). Globs: `*` and `?` match
within a name and don't match a leading dot, `**` matches any number of folders. A glob without
`/` matches names at any depth (`*_test.go`); with `/` it matches the path from the directory
(`src/legacy`, `docs/**/*.md`). A glob that matches a folder covers everything in it. Skipped
folders are entered only when a glob names them literally (`.github`, `node_modules/foo`), so
`--include '*'` never pulls in `node_modules` or `.git`. A glob that matches nothing prints a
warning, and unknown options are errors.

#### Printing part of a file

Write `path:START-END` instead of `path`, in a `--files-from` list or after `-s`. The PDF
keeps the real path and the file's own line numbers, marks what is left out ("lines 1–119
not shown"), and says which lines it shows ("Python, lines 120–180 of 1,284"). Also
`path:120-` (to the end), `path:57` (one line) and `path:10-40,90-120` (several ranges, shown
in file order). An end past the file's end is cut to it, with a note; a start past the end
is an error. A name that is itself an existing file is always printed whole. `--list-files`
prints the same form, so its output can be fed back to `--files-from`. code2txt takes the same
form: the heading says which lines it holds, and `... (lines 41-89 not shown)` marks a gap.

A range that seems to stop inside a function gets a warning, but is printed as given:
`Warning: app.py:1260-1281 stops inside a block that goes on to line 1286; to print it whole,
use app.py:1260-1286`. code2pdf reads only indentation for this, so it works in any language:
lines after the range that are indented deeper than its first line, and a closing `}` at that
line's own indent, count as the same block. code2pdf repeats the warning after `Done:`.

#### Using code2pdf from a coding agent

You can ask a coding agent (Claude Code, Codex, …) for a PDF in plain words, e.g. "print the
backend without tests and generated code, but with the SQL migrations". Tell it to:

1. read `code2pdf --help`,
2. turn the request into `--include`/`--exclude` (or pick files itself and pass them with
   `--files-from -`),
3. run with `--list-files` first and show you the list, then convert.

For example:
```bash
code2pdf -a backend --exclude tests --exclude '*_pb2.py' --include 'migrations/*.sql' --list-files
code2pdf -a backend --exclude tests --exclude '*_pb2.py' --include 'migrations/*.sql' -o backend.pdf
```

Show the version, how it was installed, and the libraries it uses (handy when reporting a problem):
```bash
$ code2pdf --version
code2pdf 3.7 (commit 1e724f3, 2026-10-11)
  installed: Homebrew, /opt/homebrew/Cellar/code2pdf/3.7
  python 3.14.8, weasyprint 70.0, pygments 2.21.0, pypdf 6.20.0
  CJK font: PingFang SC
```
`3.7+2` means two commits after release 3.7. `--version` works even when WeasyPrint is missing.

Show help:
```bash
code2pdf --help
```

Output: `-s` writes `<name>.pdf` to the current directory; `-a` writes `merged.pdf`
into the directory you converted (`-o` chooses another place). The whole directory is rendered in one pass:

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
| `--ignore-files` | Specific file names to skip (comma-separated) | - |
| `--files-from FILE` | Use exactly the files listed in `FILE` (`-` for stdin), in that order; the filters don't apply, binary files are skipped; `path:START-END` for part of a file | - |
| `-V, --version` | Show the version and how it is installed | - |

## Fonts

code2pdf bundles [IBM Plex](https://github.com/IBM/plex) Mono and Sans (in `fonts/`, SIL Open Font
License 1.1), so PDFs look the same on every machine. Plex has no Chinese, Japanese or Korean
glyphs; those come from the system fonts.

### CJK Font Support

Chinese, Japanese and Korean text works out of the box on **macOS** — the system fonts
(PingFang, Hiragino, Apple SD Gothic/Nanum) are used automatically.

On **Linux**, a CJK font must be installed, or those characters print as empty boxes.
code2pdf checks this and warns before and after converting (`install.sh --user` installs a
font automatically when none is found). With sudo: `sudo apt install fonts-noto-cjk`
(the `.deb` recommends it). **Without sudo**, the bundled script downloads Noto Sans Mono CJK
(~26 MB; it covers Chinese, Japanese and Korean, in a monospace design that keeps code columns
aligned) into `~/.local/share/fonts`:

```bash
~/.local/share/code2pdf/scripts/setup_cjk_fonts.sh      # sc (default), tc, hk, jp or kr glyph forms
```

**Full documentation**: [docs/font_installation_guide.md](docs/font_installation_guide.md)

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