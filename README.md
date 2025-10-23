# code2pdf

Convert source code files to PDF with a table of contents, preserving code formatting and making it easy to share or print your code.

## Features

- Convert single source code files to PDF
- Convert entire directories of code files to PDF with a table of contents
- Preserve syntax highlighting and formatting
- Support for 500+ programming languages (via Pygments)
- **Full UTF-8 and CJK support** (Chinese, Japanese, Korean)
- Available as a command-line tool

## Installation

### Via Homebrew (recommended for macOS users)

```bash
brew tap readbysearch/code2pdf
brew install code2pdf
```

### Manual Installation (if you are not using Homebrew)

#### Prerequisites

- Python 3 (with pip)
- Ghostscript (for PDF merging)
- jq (for JSON processing)
- Bash shell (Unix-like systems)

#### Installation Steps

1. Clone the repository
```bash
git clone https://github.com/readbysearch/code2pdf.git
cd code2pdf
```

2. Install dependencies
```bash
# macOS example
brew install python3 ghostscript jq

# Install Python packages
pip3 install --user pygments weasyprint
```

3. **(Optional) Install CJK fonts for Chinese/Japanese/Korean support**
```bash
# For Simplified Chinese (most common)
./scripts/setup_cjk_fonts.sh sc

# For other languages: tc (Traditional Chinese), jp (Japanese), kr (Korean), all (all languages)
# See docs/font_installation_guide.md for details
```

4. Make the script executable
```bash
chmod +x bin/code2pdf
```

5. Add to your PATH (optional)
```bash
ln -s "$(pwd)/bin/code2pdf" /usr/local/bin/code2pdf
```

## Usage

### Command Line Interface

Convert a single file:
```bash
code2pdf -s myfile.py
```

Convert all files in a directory:
```bash
code2pdf -a src/
```

Show help:
```bash
code2pdf --help
```

## CJK Font Support

If your code contains Chinese, Japanese, or Korean characters, you need to install CJK fonts:

```bash
# Quick setup for Simplified Chinese
./scripts/setup_cjk_fonts.sh sc
```

**Full documentation**: [docs/font_installation_guide.md](docs/font_installation_guide.md)

**Supported languages**:
- `sc` - Simplified Chinese (简体中文)
- `tc` - Traditional Chinese (繁體中文)
- `jp` - Japanese (日本語)
- `kr` - Korean (한국어)
- `all` - All CJK languages (~150 MB)

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).

- For commercial use, please [open a GitHub issue](https://github.com/readbysearch/code2pdf/issues) to discuss licensing options
- For non-commercial use, you must comply with AGPL-3.0 terms