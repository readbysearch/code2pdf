#!/bin/bash
#
# CJK Font Setup Script for code2pdf
# Installs Noto Sans CJK fonts for Chinese/Japanese/Korean support
#
# Usage: ./setup_cjk_fonts.sh [language]
#   language: sc (Simplified Chinese), tc (Traditional Chinese),
#             jp (Japanese), kr (Korean), all (all languages)
#   Default: sc (Simplified Chinese)

set -e  # Exit on error

LANGUAGE="${1:-sc}"
FONT_DIR="$HOME/.local/share/fonts/noto-cjk"
DOWNLOAD_URL="https://github.com/googlefonts/noto-cjk/releases/download/Sans2.004/01_NotoSansCJK-OTF-VF.zip"
TEMP_DIR="/tmp/noto-cjk-install-$$"

echo "========================================"
echo "code2pdf CJK Font Installer"
echo "========================================"
echo ""

# Check for required commands
check_dependencies() {
    local missing=()
    for cmd in wget python3 fc-cache; do
        if ! command -v $cmd &> /dev/null; then
            missing+=($cmd)
        fi
    done

    if [ ${#missing[@]} -ne 0 ]; then
        echo "Error: Missing required dependencies: ${missing[*]}"
        echo "Please install them first."
        exit 1
    fi
}

# Show usage
show_usage() {
    echo "Usage: $0 [LANGUAGE]"
    echo ""
    echo "Languages:"
    echo "  sc    Simplified Chinese (简体中文) [default]"
    echo "  tc    Traditional Chinese (繁體中文)"
    echo "  jp    Japanese (日本語)"
    echo "  kr    Korean (한국어)"
    echo "  all   All CJK languages"
    echo ""
    echo "Examples:"
    echo "  $0         # Install Simplified Chinese fonts"
    echo "  $0 jp      # Install Japanese fonts"
    echo "  $0 all     # Install all CJK fonts"
    exit 0
}

# Parse arguments
if [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    show_usage
fi

case "$LANGUAGE" in
    sc|SC)
        LANGUAGE="sc"
        LANGUAGE_NAME="Simplified Chinese"
        ;;
    tc|TC)
        LANGUAGE="tc"
        LANGUAGE_NAME="Traditional Chinese"
        ;;
    jp|JP)
        LANGUAGE="jp"
        LANGUAGE_NAME="Japanese"
        ;;
    kr|KR)
        LANGUAGE="kr"
        LANGUAGE_NAME="Korean"
        ;;
    all|ALL)
        LANGUAGE="all"
        LANGUAGE_NAME="All CJK Languages"
        ;;
    *)
        echo "Error: Unknown language '$LANGUAGE'"
        echo "Run '$0 --help' for usage information."
        exit 1
        ;;
esac

echo "Installing fonts for: $LANGUAGE_NAME"
echo ""

# Check dependencies
echo "[1/6] Checking dependencies..."
check_dependencies
echo "✓ All dependencies found"
echo ""

# Create directories
echo "[2/6] Creating directories..."
mkdir -p "$FONT_DIR"
mkdir -p "$TEMP_DIR"
echo "✓ Font directory: $FONT_DIR"
echo ""

# Download fonts
echo "[3/6] Downloading Noto Sans CJK fonts..."
echo "Source: $DOWNLOAD_URL"
cd "$TEMP_DIR"
if wget -q --show-progress "$DOWNLOAD_URL"; then
    echo "✓ Download complete"
else
    echo "✗ Download failed"
    rm -rf "$TEMP_DIR"
    exit 1
fi
echo ""

# Extract fonts
echo "[4/6] Extracting fonts..."
python3 -m zipfile -e 01_NotoSansCJK-OTF-VF.zip .
echo "✓ Extraction complete"
echo ""

# Install fonts based on language selection
echo "[5/6] Installing fonts..."
case "$LANGUAGE" in
    sc)
        cp Variable/OTF/Subset/NotoSansSC-VF.otf "$FONT_DIR/"
        cp Variable/OTF/Mono/NotoSansMonoCJKsc-VF.otf "$FONT_DIR/"
        echo "✓ Installed Simplified Chinese fonts"
        ;;
    tc)
        cp Variable/OTF/Subset/NotoSansTC-VF.otf "$FONT_DIR/"
        cp Variable/OTF/Mono/NotoSansMonoCJKtc-VF.otf "$FONT_DIR/"
        echo "✓ Installed Traditional Chinese fonts"
        ;;
    jp)
        cp Variable/OTF/Subset/NotoSansJP-VF.otf "$FONT_DIR/"
        cp Variable/OTF/Mono/NotoSansMonoCJKjp-VF.otf "$FONT_DIR/"
        echo "✓ Installed Japanese fonts"
        ;;
    kr)
        cp Variable/OTF/Subset/NotoSansKR-VF.otf "$FONT_DIR/"
        cp Variable/OTF/Mono/NotoSansMonoCJKkr-VF.otf "$FONT_DIR/"
        echo "✓ Installed Korean fonts"
        ;;
    all)
        cp Variable/OTF/Subset/*.otf "$FONT_DIR/"
        cp Variable/OTF/Mono/*.otf "$FONT_DIR/"
        echo "✓ Installed all CJK fonts"
        ;;
esac
echo ""

# Update font cache
echo "[6/6] Updating font cache..."
fc-cache -f "$FONT_DIR"
echo "✓ Font cache updated"
echo ""

# Verify installation
echo "Verifying installation..."
INSTALLED_FONTS=$(fc-list | grep -i "noto.*cjk" | wc -l)
if [ "$INSTALLED_FONTS" -gt 0 ]; then
    echo "✓ Successfully installed $INSTALLED_FONTS font variants"
    echo ""
    echo "Installed fonts:"
    fc-list | grep -i "noto.*cjk" | sed 's/^/  - /'
else
    echo "✗ Warning: No fonts detected. Installation may have failed."
    echo "  Try running: fc-cache -fv $FONT_DIR"
fi
echo ""

# Cleanup
echo "Cleaning up temporary files..."
rm -rf "$TEMP_DIR"
echo "✓ Cleanup complete"
echo ""

# Show disk usage
FONT_SIZE=$(du -sh "$FONT_DIR" | cut -f1)
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo "Font directory: $FONT_DIR"
echo "Disk space used: $FONT_SIZE"
echo ""
echo "Next steps:"
echo "1. Test with: code2pdf -s your_file_with_cjk_text.py"
echo "2. Verify CJK characters render correctly in the PDF"
echo ""
echo "For troubleshooting, see: docs/font_installation_guide.md"
