#!/bin/bash

# Check if a file path was provided
if [ -z "$1" ]; then
  echo "No file path provided." >&2
  exit 1
fi

# Check if the project folder path was provided
if [ -z "$2" ]; then
  echo "No project folder path provided." >&2
  exit 1
fi

# Check if the file exists (FILE:START-END prints part of it; code_to_pdf.py checks the range)
file_path="$1"
if [ ! -f "$file_path" ] && [[ "$file_path" =~ ^(.+):[0-9][0-9,-]*$ ]] && [ -f "${BASH_REMATCH[1]}" ]; then
  file_path="${BASH_REMATCH[1]}"
fi
if [ ! -f "$file_path" ]; then
  echo "File not found." >&2
  exit 1
fi

file_name="$1"
vs_project_folder_name="$2"
output="${3:-}"   # optional: the PDF path, or a folder for <name>.pdf

# Function to generate a PDF file name
generate_pdf_file_name() {
    # File name without its last extension, in plain bash (`rev` is missing on minimal Ubuntu)
    local name="${1##*/}"
    echo "${name%.*}"
}

echo "Converting to a PDF file for $file_name"

pdf_name=$(generate_pdf_file_name "$file_path")
if [ -z "$output" ]; then
    output="$vs_project_folder_name/$pdf_name.pdf"
elif [ -d "$output" ]; then
    output="${output%/}/$pdf_name.pdf"
fi

# Get the directory where this script is located
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# exec, so a signal sent to code2pdf reaches Python (it reports errors and where the PDF went)
exec python3 "$script_dir/code_to_pdf.py" "$file_name" "$output" "$file_name"
