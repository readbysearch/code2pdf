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

# Check if the file exists
if [ ! -f "$1" ]; then
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

pdf_name=$(generate_pdf_file_name "$file_name")
if [ -z "$output" ]; then
    output="$vs_project_folder_name/$pdf_name.pdf"
elif [ -d "$output" ]; then
    output="${output%/}/$pdf_name.pdf"
fi

# Get the directory where this script is located
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Convert the file to PDF using Python script with UTF-8 support (it reports where the PDF went)
if ! python3 "$script_dir/code_to_pdf.py" "$file_name" "$output" "$file_name"; then
    echo "Error: Failed to create PDF" >&2
    exit 1
fi
