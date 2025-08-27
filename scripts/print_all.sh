#!/bin/bash
declare -a visited_dirs=() # to avoid symbolic link recursion

# If no argument is provided, use current directory as default
# Convert ROOT_DIR to absolute path immediately when setting it
ROOT_DIR=$(cd "${1:-.}" && pwd)

# Get vimrc path
VIMRC_PATH=$2

# These are the arguments passed from the main script
BLACKLISTED_FOLDERS_JSON=$3
BLACKLISTED_FOLDER_PATTERN=$4
WHITELISTED_FILE_EXTENSIONS_JSON=$5
WHITELISTED_FILE_NAMES_JSON=$6
INCLUDE_NO_EXTENSION=${7:-true}  # default value "true" means processing the files without extension, such as Dockerfile, vimrc, LICENSE, and Makefile.
BLACKLISTED_FILES_JSON=${8:-'[]'}  # JSON array of specific files to ignore
BLACKLISTED_TYPES_JSON=${9:-'[]'}  # JSON array of file extensions to ignore
ADDITIONAL_BLACKLIST_FOLDERS_JSON=${10:-'[]'}  # Additional folders to skip
INCLUDE_TYPES_JSON=${11:-'[]'}  # If specified, only include these types

vim --version >&2
echo "DEBUG: Starting script execution..." >&2
echo "DEBUG: Working directory: $(pwd)" >&2
echo "DEBUG: ROOT_DIR: $ROOT_DIR" >&2

# Count lines in all .ts files excluding those in node_modules and display file names
# find "$ROOT_DIR" -name "node_modules" -prune -o -name "*$EXTENSION" -type f -print | xargs wc -l
echo "printing all src files in $ROOT_DIR"

##########################################3
# Step 1. Print all src files into /tmp/ 
##########################################3

# Change src/components/Task.js to src____components____Task----js
generate_pdf_file_name () {
    orig_name="$1"
    output=$( echo "$orig_name" | perl -pe 's/\//____/g and s/\./----/g' )
    echo "$output"
}

print_to_pdf () {
    file_name="$1"
    echo "DEBUG: ===================" >&2
    echo "DEBUG: Converting file: $file_name" >&2
    echo "DEBUG: Starting vim conversion..." >&2
    pdf_name="$( generate_pdf_file_name "$file_name")"
    # Check if the input is empty or has unexpected characters
    if [[ -z $pdf_name ]]; then
        echo "Error: pdf_name is empty."
        exit 1
    fi
    echo "DEBUG: generated pdf_name in /tmp folder: $pdf_name" >&2
    vim -u "$VIMRC_PATH" -n -c "set noswapfile" -c "set nobackup" -c "set nowritebackup" -c "syntax on" "+set stl+=%{expand('%:~:.')}" "+hardcopy > /tmp/$pdf_name.ps" "+wq" "$file_name"
    echo "DEBUG: Vim conversion complete" >&2
    echo "DEBUG: Converting PS to PDF..." >&2
    ps2pdf "/tmp/$pdf_name.ps" "/tmp/$pdf_name.pdf"
}

print_files_in_a_folder() {
    # Quoted assignment, in case $1 has spaces
    folder="$1"

    # Parse the JSON strings into bash arrays
    declare -a blacklisted_folders=($(echo "$BLACKLISTED_FOLDERS_JSON" | jq -r '.[]'))
    blacklisted_folder_pattern="$BLACKLISTED_FOLDER_PATTERN"
    declare -a whitelisted_file_extensions=($(echo "$WHITELISTED_FILE_EXTENSIONS_JSON" | jq -r '.[]'))
    declare -a whitelisted_file_names=($(echo "$WHITELISTED_FILE_NAMES_JSON" | jq -r '.[]'))
    declare -a blacklisted_file_names=($(echo "$BLACKLISTED_FILES_JSON" | jq -r '.[]'))
    declare -a blacklisted_types=($(echo "$BLACKLISTED_TYPES_JSON" | jq -r '.[]'))
    declare -a additional_blacklist_folders=($(echo "$ADDITIONAL_BLACKLIST_FOLDERS_JSON" | jq -r '.[]'))
    declare -a include_types=($(echo "$INCLUDE_TYPES_JSON" | jq -r '.[]'))
    include_no_extension="$INCLUDE_NO_EXTENSION"

    # Check if the folder's basename is in the blacklist array
    folder_basename=$(basename "$folder")
    for blacklist in "${blacklisted_folders[@]}"; do
    if [[ "$folder_basename" == "$blacklist" ]]; then
        echo "DEBUG: Skipping blacklisted folder: $folder" >&2
        return
    fi
    done
    
    # Check additional blacklisted folders
    for blacklist in "${additional_blacklist_folders[@]}"; do
    if [[ "$folder_basename" == "$blacklist" ]]; then
        echo "DEBUG: Skipping additional blacklisted folder: $folder" >&2
        return
    fi
    done

    # Check if the folder's basename matches the blacklisted pattern (e.g. env*)
    if [[ "$folder_basename" == $blacklisted_folder_pattern ]]; then
        echo "DEBUG: Skipping folder matching blacklisted pattern: $folder" >&2
        return
    fi

    echo "DEBUG: Processing folder: $folder" >&2

    # The quoted glob handles any folder with spaces
    for entry in "$folder"/*; do
        # Skip if it doesn't exist (e.g. empty folder)
        [ -e "$entry" ] || continue

        if [ -f "$entry" ]; then
            # File handling
            base_name=$(basename "$entry")
            filename="${base_name%.*}"      # text before the last dot
            extension="${base_name##*.}"    # text after the last dot
            process_file=false

            echo "DEBUG: Processing file: $entry" >&2
            echo "DEBUG: filename: $filename" >&2
            echo "DEBUG: extension: $extension" >&2
            echo "DEBUG: include_no_extension: $include_no_extension" >&2

            # Check if file is in the blacklisted files
            for blacklisted_file in "${blacklisted_file_names[@]}"; do
                if [ "$base_name" = "$blacklisted_file" ]; then
                    echo "DEBUG: Skipping blacklisted file: $base_name" >&2
                    continue 2  # Skip to next file in outer loop
                fi
            done
            
            # Check if extension is in the blacklisted types
            for blacklisted_type in "${blacklisted_types[@]}"; do
                if [ "$extension" = "$blacklisted_type" ]; then
                    echo "DEBUG: Skipping blacklisted type: $extension" >&2
                    continue 2  # Skip to next file in outer loop
                fi
            done
            
            # If include_types is specified, only process those types
            if [ "${#include_types[@]}" -gt 0 ]; then
                process_file=false
                for include_type in "${include_types[@]}"; do
                    if [ "$extension" = "$include_type" ]; then
                        echo "DEBUG: Including specified type: $extension" >&2
                        process_file=true
                        break
                    fi
                done
                # If extension doesn't match include_types, skip this file
                if [ "$process_file" = false ]; then
                    continue
                fi
            else
                # Normal processing: check against whitelist
                # Handle files without extension
                if [ "$filename" == "$extension" ] && [ "$include_no_extension" == "true" ]; then
                    echo "DEBUG: Found file without extension, setting process_file=true" >&2
                    process_file=true
                else
                    # Check if the extension is in the whitelist
                    for allowed_extension in "${whitelisted_file_extensions[@]}"; do
                        if [ "$extension" == "$allowed_extension" ]; then
                            process_file=true
                            break
                        fi
                    done
                fi
            fi

            # Check if the whole filename is in the whitelist
            for allowed_name in "${whitelisted_file_names[@]}"; do
                if [ "$base_name" == "$allowed_name" ]; then
                    process_file=true
                    break
                fi
            done

            # If flagged for processing, convert to PDF
            if [ "$process_file" == "true" ]; then
                print_to_pdf "$entry"
                echo "PROGRESS: Processed $entry" >&2
            fi

        else
            # Subdirectory handling
            real_path=$(realpath "$entry")

            # Avoid infinite recursion by tracking visited directories
            if ! printf '%s\n' "${visited_dirs[@]}" | grep -qxF "$real_path"; then
                visited_dirs+=("$real_path")
                print_files_in_a_folder "$entry"
            else
                echo "DEBUG: Skipping already visited directory: $entry" >&2
            fi
        fi
    done
}

rm /tmp/*.ps
rm /tmp/*.pdf
print_files_in_a_folder "$ROOT_DIR"


##########################################3
# Step 2. Generate the table of table_of_contents
##########################################3

# Change src____components____Task----js.pdf to src/components/Task.js
generate_orig_file_name () {
    pdf_name="$1"
    output=$( echo "$pdf_name" | perl -pe 's/\.pdf//g and s/____/\//g and s/----/\./g' )
    echo "$output"
}

cd /tmp
rm table_of_contents
touch table_of_contents

echo "generating the table of contents"
for entry in *.pdf; do
    orig_file_name="$( generate_orig_file_name "$entry" )"
    echo "$orig_file_name" >> table_of_contents
done
echo "Info: Contents of table_of_contents:" >&2
cat table_of_contents >&2

vim -u "$VIMRC_PATH" "+hardcopy > 00_table_of_contents.ps" "+wq" table_of_contents
ps2pdf 00_table_of_contents.ps 00_table_of_contents.pdf

##########################################3
# Step 3. Merge all /tmp/*.pdf into a single pdf
##########################################3
echo "Debug: Starting final merge step..." >&2
echo "Debug: Current working directory: $(pwd)" >&2
echo "Debug: ROOT_DIR value: $ROOT_DIR" >&2

# Clean up any existing merged PDF
echo "Debug: Removing any existing merged.pdf" >&2
rm -f "$ROOT_DIR/merged.pdf"

# Merge PDFs with explicit error checking
echo "merging all pdf files into a single file named merged.pdf" >&2
if ! gs -q -dNOPAUSE -dBATCH -sDEVICE=pdfwrite -sOutputFile=/tmp/merged.pdf /tmp/*.pdf >&2; then
    echo "Error: PDF merge failed" >&2
    exit 1
fi

# Check if merge was successful
if [ ! -f "/tmp/merged.pdf" ]; then
    echo "Error: Merged PDF was not created" >&2
    exit 1
fi

# Move with explicit error checking
echo "Debug: Moving merged PDF to final location" >&2
if ! mv "/tmp/merged.pdf" "$ROOT_DIR/merged.pdf"; then
    echo "Error: Failed to move merged PDF" >&2
    exit 1
fi

# Verify final file exists
if [ -f "$ROOT_DIR/merged.pdf" ]; then
    echo "Success: PDF created at $ROOT_DIR/merged.pdf" >&2
    ls -l "$ROOT_DIR/merged.pdf" >&2
else
    echo "Error: Final PDF not found at expected location" >&2
    exit 1
fi
