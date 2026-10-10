#!/bin/bash
#
# CJK Font Setup Script for code2pdf
# Installs Noto Sans Mono CJK (Regular + Bold, ~26 MB download) into ~/.local/share/fonts/noto-cjk.
# No sudo needed. Every Noto CJK font covers Chinese, Japanese and Korean; the language only
# picks the regional glyph forms.
#
# Usage: ./setup_cjk_fonts.sh [language]
#   language: sc (Simplified Chinese, default), tc (Traditional Chinese), hk (Hong Kong),
#             jp (Japanese), kr (Korean); "all" is accepted and installs sc
#
# Needs curl or wget, and Python or unzip/bsdtar to unpack. Runs fc-cache if available.

set -euo pipefail

LANGUAGE="${1:-sc}"
# Release asset numbers of Noto Sans Mono CJK in notofonts/noto-cjk Sans2.004 (plain bash 3 syntax)
case "$LANGUAGE" in
    jp) ASSET="11" ;;
    kr) ASSET="12" ;;
    sc|all) LANGUAGE="sc"; ASSET="13" ;;
    tc) ASSET="14" ;;
    hk) ASSET="15" ;;
    *) echo "Unknown language '$LANGUAGE' (use sc, tc, hk, jp or kr)" >&2; exit 1 ;;
esac
LABEL="$(echo "$LANGUAGE" | tr '[:lower:]' '[:upper:]')"

FONT_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/fonts/noto-cjk"
URL="https://github.com/notofonts/noto-cjk/releases/download/Sans2.004/${ASSET}_NotoSansMonoCJK${LANGUAGE}.zip"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

# Tools from code2pdf's own environment count too (e.g. a conda-forge install has its own python3 and fc-cache)
export PATH="$PATH:$SCRIPT_DIR/../venv/bin"

echo "Installing Noto Sans Mono CJK $LABEL into $FONT_DIR"
echo "Downloading $URL"
if command -v curl >/dev/null 2>&1; then
    curl -fL --progress-bar "$URL" -o "$TEMP_DIR/fonts.zip"
elif command -v wget >/dev/null 2>&1; then
    wget -q --show-progress "$URL" -O "$TEMP_DIR/fonts.zip"
else
    echo "Error: needs curl or wget" >&2
    exit 1
fi

if command -v python3 >/dev/null 2>&1; then
    python3 -m zipfile -e "$TEMP_DIR/fonts.zip" "$TEMP_DIR/x"
elif command -v unzip >/dev/null 2>&1; then
    unzip -q "$TEMP_DIR/fonts.zip" -d "$TEMP_DIR/x"
elif command -v bsdtar >/dev/null 2>&1; then
    mkdir -p "$TEMP_DIR/x" && bsdtar -xf "$TEMP_DIR/fonts.zip" -C "$TEMP_DIR/x"
else
    echo "Error: needs python3, unzip or bsdtar to unpack the fonts" >&2
    exit 1
fi

mkdir -p "$FONT_DIR"
find "$TEMP_DIR/x" -name '*.otf' -exec cp {} "$FONT_DIR/" \;
find "$TEMP_DIR/x" -name 'LICENSE*' -exec cp {} "$FONT_DIR/LICENSE-Noto-CJK.txt" \;
echo "Installed: $(cd "$FONT_DIR" && ls *.otf | tr '\n' ' ')"

if command -v fc-cache >/dev/null 2>&1; then
    fc-cache -f "$FONT_DIR" >/dev/null 2>&1 || true
fi

if command -v fc-list >/dev/null 2>&1; then
    if fc-list ":charset=4e2d" family | grep -q "Noto Sans Mono CJK"; then
        echo "Done: fontconfig finds Noto Sans Mono CJK; Chinese/Japanese/Korean text will render in code2pdf."
    else
        echo "Warning: the fonts are in $FONT_DIR but fontconfig doesn't list them yet." >&2
        echo "  Try: fc-cache -f \"$FONT_DIR\"" >&2
        exit 1
    fi
else
    echo "Done (fc-list not available to double-check)."
fi
