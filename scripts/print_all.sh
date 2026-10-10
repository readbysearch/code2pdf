#!/bin/bash
# Convert every selected source file under a directory into ROOT_DIR/merged.pdf
# (table of contents first). Rendering is done in one pass by dir_to_pdf.py.
#
# Arguments (passed by bin/code2pdf):
#   1 ROOT_DIR  2 BLACKLISTED_FOLDERS_JSON  3 BLACKLISTED_FOLDER_PATTERN
#   4 WHITELISTED_FILE_EXTENSIONS_JSON  5 WHITELISTED_FILE_NAMES_JSON
#   6 INCLUDE_NO_EXTENSION  7 IGNORE_FILES  8 IGNORE_TYPES  9 IGNORE_FOLDERS  10 INCLUDE_TYPES
#   11... extra options for dir_to_pdf.py (e.g. --list-files)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# If no argument is provided, use current directory as default
ROOT_DIR=$(cd "${1:-.}" 2>/dev/null && pwd) || { echo "Error: directory not found: ${1:-.}" >&2; exit 1; }
# Before v3.8, argument 2 was a vimrc path; refuse the old form instead of shifting everything silently
[[ "${2:-}" == *vimrc ]] && { echo "Error: print_all.sh no longer takes a vimrc path as argument 2" >&2; exit 2; }

exec python3 "$SCRIPT_DIR/dir_to_pdf.py" "$ROOT_DIR" "$ROOT_DIR/merged.pdf" \
    "$2" "$3" "$4" "$5" "${6:-true}" "${7:-}" "${8:-}" "${9:-}" "${10:-}" "${@:11}"
