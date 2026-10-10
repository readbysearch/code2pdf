#!/bin/bash
# Convert every selected source file under a directory into ROOT_DIR/merged.pdf
# (table of contents first). Rendering is done in one pass by dir_to_pdf.py.
#
# Arguments (passed by bin/code2pdf):
#   1 ROOT_DIR  2 VIMRC_PATH (unused, kept for compatibility)
#   3 BLACKLISTED_FOLDERS_JSON  4 BLACKLISTED_FOLDER_PATTERN
#   5 WHITELISTED_FILE_EXTENSIONS_JSON  6 WHITELISTED_FILE_NAMES_JSON
#   7 INCLUDE_NO_EXTENSION  8 IGNORE_FILES  9 IGNORE_TYPES  10 IGNORE_FOLDERS  11 INCLUDE_TYPES

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# If no argument is provided, use current directory as default
ROOT_DIR=$(cd "${1:-.}" 2>/dev/null && pwd) || { echo "Error: directory not found: ${1:-.}" >&2; exit 1; }

exec python3 "$SCRIPT_DIR/dir_to_pdf.py" "$ROOT_DIR" "$ROOT_DIR/merged.pdf" \
    "$3" "$4" "$5" "$6" "${7:-true}" "${8:-}" "${9:-}" "${10:-}" "${11:-}"
