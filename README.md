# code2pdf

Convert source code files to PDF or combine them into a single text file, with table of contents and syntax highlighting, optimized for sharing, printing, or LLM context input.

## Features

### code2pdf
- Convert single source code files to PDF
- Convert entire directories of code files to PDF with a table of contents
- Preserve syntax highlighting and formatting
- Support for 500+ programming languages (via Pygments)
- **Full UTF-8 and CJK support** (Chinese, Japanese, Korean)
- Available as a command-line tool

### code2txt
- Combine source code files into a single text file
- Generate markdown-formatted output optimized for LLM context
- Configurable file filtering and size limits
- Automatic language detection for syntax highlighting
- Table of contents generation

## Installation

### Quick Install Script (Linux - Recommended)

Install both tools with a single command:

```bash
# Install for current user (no sudo required)
curl -sSL https://raw.githubusercontent.com/waleking/code2pdf/main/install.sh | bash -s -- --user

# Or install system-wide (requires sudo)
curl -sSL https://raw.githubusercontent.com/waleking/code2pdf/main/install.sh | bash -s -- --system

# Interactive installation (choose user/system during install)
curl -sSL https://raw.githubusercontent.com/waleking/code2pdf/main/install.sh | bash
```

**Install Script Features:**
- ✅ Automatic dependency checking
- ✅ Cross-platform Linux support  
- ✅ User or system-wide installation
- ✅ Automatic PATH configuration
- ✅ Works on Ubuntu, CentOS, Fedora, RHEL, etc.

### Via Homebrew (macOS users)

```bash
brew tap readbysearch/code2pdf
brew install code2pdf
```

### Manual Installation

#### Prerequisites

For code2pdf:
- Python 3 (with pip)
- Ghostscript (for PDF merging)
- jq (for JSON processing)
- Bash shell (Unix-like systems)

For code2txt:
- Bash shell (Unix-like systems)
- No additional dependencies required

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

4. Make the scripts executable
```bash
chmod +x bin/code2pdf bin/code2txt
chmod +x scripts/*.sh
```

5. Add to your PATH (optional)
```bash
ln -s "$(pwd)/bin/code2pdf" /usr/local/bin/code2pdf
ln -s "$(pwd)/bin/code2txt" /usr/local/bin/code2txt
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

1. Set up test environment:
```bash
python3 -m venv test_venv
source test_venv/bin/activate
pip install -r requirements-test.txt
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