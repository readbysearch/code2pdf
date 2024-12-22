#!/bin/bash
declare -a visited_dirs=() # to avoid symbolic link recursion

# If no argument is provided, use current directory as default
R# Convert ROOT_DIR to absolute path immediately when setting it
ROOT_DIR=$(cd "${1:-.}" && pwd)

# Get vimrc path
VIMRC_PATH=$2

# These are the arguments passed from TypeScript
BLACKLISTED_FOLDERS_JSON=$3
BLACKLISTED_FOLDER_PATTERN=$4
WHITELISTED_FILE_EXTENSIONS_JSON=$5
WHITELISTED_FILE_NAMES_JSON=$6
INCLUDE_NO_EXTENSION=${7:-true}  # default value "true" means processing the files without extension, such as Dockerfile, vimrc, LICENSE, and Makefile.

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
    orig_name=$1
    output=$( echo "$orig_name" | perl -pe 's/\//____/g and s/\./----/g' )
    echo "$output"
}

print_to_pdf () {
    file_name=$1
    echo "DEBUG: ===================" >&2
    echo "DEBUG: Converting file: $file_name" >&2
    echo "DEBUG: Starting vim conversion..." >&2
    pdf_name=$( generate_pdf_file_name $file_name)
    vim -u "$VIMRC_PATH" -c "syntax on" "+set stl+=%{expand('%:~:.')}" "+hardcopy > /tmp/$pdf_name.ps" "+wq" $file_name
    echo "DEBUG: Vim conversion complete" >&2
    echo "DEBUG: Converting PS to PDF..." >&2
    ps2pdf /tmp/$pdf_name.ps /tmp/$pdf_name.pdf
}

print_files_in_a_folder() {
    folder=$1

    # Parse the JSON strings into bash arrays
    declare -a blacklisted_folders=($(echo "$BLACKLISTED_FOLDERS_JSON" | jq -r '.[]'))
    blacklisted_folder_pattern="$BLACKLISTED_FOLDER_PATTERN"
    declare -a whitelisted_file_extensions=($(echo "$WHITELISTED_FILE_EXTENSIONS_JSON" | jq -r '.[]'))
    declare -a whitelisted_file_names=($(echo "$WHITELISTED_FILE_NAMES_JSON" | jq -r '.[]'))
    include_no_extension="$INCLUDE_NO_EXTENSION"

    # Check if the folder is in the blacklist
    folder_basename=$(basename "$folder")

    for blacklist in "${blacklisted_folders[@]}"
    do
        if [[ "$folder_basename" == "$blacklist" ]]; then
            return
        fi
    done

    # Handle env* pattern separately
    if [[ "$folder_basename" == $blacklisted_folder_pattern ]]; then
        return
    fi

    echo "DEBUG: Processing folder: $folder" >&2
    for entry in "$folder"/*
    do
        if [ -f "$entry" ]
        then
            base_name=$(basename "$entry")
            filename="${base_name%.*}"
            extension="${base_name##*.}"
            process_file=false

            # Debug information for extension checking
            echo "DEBUG: Processing file: $entry" >&2
            echo "DEBUG: filename: $filename" >&2
            echo "DEBUG: extension: $extension" >&2
            echo "DEBUG: include_no_extension value: $include_no_extension" >&2
            # Handle files without extension
            if [ "$filename" == "$extension" ] && [ "$include_no_extension" == "true" ]; then
                echo "DEBUG: Found file without extension, setting process_file=true" >&2
                process_file=true
            else
                # Check if the file's extension is in the whitelist
                for allowed_extension in "${whitelisted_file_extensions[@]}"
                do
                    if [ "$extension" == "$allowed_extension" ]; then
                        process_file=true
                        break
                    fi
                done
            fi

            # Check if the file's name is in the whitelist
            for allowed_name in "${whitelisted_file_names[@]}"
            do
                if [ "$base_name" == "$allowed_name" ]; then
                    process_file=true
                    break
                fi
            done

            if [ "$process_file" = true ]; then
                print_to_pdf "$entry"

                # Emit progress info
                echo "PROGRESS: Processed $entry" >&2
            fi
        else
            # further visit the files or folders in the current folder
            # and also avoid symbolic link recursion
            real_path=$(realpath "$entry")
            if [[ ! " ${visited_dirs[@]} " =~ " ${real_path} " ]]; then
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
print_files_in_a_folder $ROOT_DIR 


##########################################3
# Step 2. Generate the table of table_of_contents
##########################################3

# Change src____components____Task----js.pdf to src/components/Task.js
generate_orig_file_name () {
    pdf_name=$1
    output=$( echo "$pdf_name" | perl -pe 's/\.pdf//g and s/____/\//g and s/----/\./g' )
    echo "$output"
}

cd /tmp
rm table_of_contents
touch table_of_contents

echo "generating the table of contents"
for entry in *.pdf
do
    orig_file_name=$( generate_orig_file_name $entry )
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
