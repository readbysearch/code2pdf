#!/bin/bash

# Check if a file path was provided
if [ -z "$1" ]; then
  echo "No file path provided."
  exit 1
fi

# Check if the project folder path was provided
if [ -z "$2" ]; then
  echo "No project folder path provided."
  exit 1
fi

# Check if the file exists
if [ ! -f "$1" ]; then
  echo "File not found."
  exit 1
fi

file_name="$1"
vs_project_folder_name="$2"

# Function to generate a PDF file name
generate_pdf_file_name() {
    # Extract the file name from the full path and remove the extension
    basename "$1" | rev | cut -d. -f2- | rev
}

echo "Converting to a PDF file for $file_name"

pdf_name=$(generate_pdf_file_name "$file_name")

# Get the directory where this script is located
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Convert the file to PDF using Python script with UTF-8 support
python3 "$script_dir/code_to_pdf.py" "$file_name" "$vs_project_folder_name/$pdf_name.pdf" "$file_name"

# Check if PDF was created successfully
if [ $? -eq 0 ]; then
    echo "PDF created at $vs_project_folder_name/$pdf_name.pdf"
else
    echo "Error: Failed to create PDF"
    exit 1
fi
