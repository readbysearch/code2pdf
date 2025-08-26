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

echo "/tmp/$pdf_name.ps"

# Convert the file to PDF using Vim
vim -n -c "set noswapfile" -c "set nobackup" -c "set nowritebackup" "+set stl+=%{expand('%:~:.')}" "+hardcopy > /tmp/$pdf_name.ps" "+wq" "$file_name"

# Convert the PostScript file to PDF
ps2pdf "/tmp/$pdf_name.ps" "/tmp/$pdf_name.pdf"

# Move the PDF to the project folder
mv "/tmp/$pdf_name.pdf" "$vs_project_folder_name/$pdf_name.pdf"

echo "PDF created at $vs_project_folder_name/$pdf_name"
