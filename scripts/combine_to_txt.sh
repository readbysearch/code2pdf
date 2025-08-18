#!/usr/bin/env bash

# Arguments from main script
TARGET_DIR="$1"
OUTPUT_FILE="$2"
IGNORE_TYPES="$3"
IGNORE_FOLDERS="$4"
INCLUDE_TYPES="$5"
MAX_FILE_SIZE="$6"
NO_TOC="$7"
VERBOSE="$8"

# Track visited directories to prevent symbolic link recursion
declare -a visited_dirs=()
declare -a processed_files=()

# Convert comma-separated lists to arrays
IFS=',' read -ra IGNORE_TYPES_ARRAY <<< "$IGNORE_TYPES"
IFS=',' read -ra IGNORE_FOLDERS_ARRAY <<< "$IGNORE_FOLDERS"
if [ -n "$INCLUDE_TYPES" ]; then
    IFS=',' read -ra INCLUDE_TYPES_ARRAY <<< "$INCLUDE_TYPES"
fi

# Function to get file extension to language mapping
get_language_from_extension() {
    local file="$1"
    local basename="$(basename "$file")"
    local extension="${basename##*.}"
    
    # Handle files without extension
    if [ "$basename" = "$extension" ]; then
        case "$basename" in
            Dockerfile) echo "dockerfile" ;;
            Makefile|makefile) echo "makefile" ;;
            .gitignore|.dockerignore) echo "text" ;;
            .env*) echo "bash" ;;
            *) echo "text" ;;
        esac
        return
    fi
    
    # Map extensions to languages
    case "$extension" in
        js|mjs|cjs) echo "javascript" ;;
        ts|tsx) echo "typescript" ;;
        jsx) echo "javascript" ;;
        py) echo "python" ;;
        java) echo "java" ;;
        c) echo "c" ;;
        cpp|cc|cxx) echo "cpp" ;;
        h|hpp) echo "cpp" ;;
        cs) echo "csharp" ;;
        go) echo "go" ;;
        rs) echo "rust" ;;
        rb) echo "ruby" ;;
        php) echo "php" ;;
        swift) echo "swift" ;;
        kt|kts) echo "kotlin" ;;
        scala) echo "scala" ;;
        sh|bash) echo "bash" ;;
        zsh) echo "zsh" ;;
        ps1) echo "powershell" ;;
        bat|cmd) echo "batch" ;;
        html|htm) echo "html" ;;
        css) echo "css" ;;
        scss|sass) echo "scss" ;;
        less) echo "less" ;;
        xml) echo "xml" ;;
        json) echo "json" ;;
        yaml|yml) echo "yaml" ;;
        toml) echo "toml" ;;
        md|markdown) echo "markdown" ;;
        rst) echo "rst" ;;
        sql) echo "sql" ;;
        r|R) echo "r" ;;
        m) echo "matlab" ;;
        jl) echo "julia" ;;
        lua) echo "lua" ;;
        pl) echo "perl" ;;
        vim) echo "vim" ;;
        el) echo "elisp" ;;
        *) echo "text" ;;
    esac
}

# Function to convert size string to bytes
size_to_bytes() {
    local size="$1"
    local number="${size//[^0-9]/}"
    local unit="${size//[0-9]/}"
    
    case "$unit" in
        K|k) echo $((number * 1024)) ;;
        M|m) echo $((number * 1024 * 1024)) ;;
        G|g) echo $((number * 1024 * 1024 * 1024)) ;;
        *) echo "$number" ;;
    esac
}

# Function to check if file should be processed
should_process_file() {
    local file="$1"
    local basename="$(basename "$file")"
    local extension="${basename##*.}"
    
    # If file has no extension, extension equals basename
    if [ "$basename" = "$extension" ]; then
        extension=""
    fi
    
    # Check file size
    if [ -n "$MAX_FILE_SIZE" ]; then
        local max_bytes=$(size_to_bytes "$MAX_FILE_SIZE")
        # Cross-platform stat command
        if [[ "$OSTYPE" == "darwin"* ]]; then
            local file_size=$(stat -f%z "$file" 2>/dev/null)
        else
            local file_size=$(stat -c%s "$file" 2>/dev/null)
        fi
        if [ -n "$file_size" ] && [ "$file_size" -gt "$max_bytes" ]; then
            [ "$VERBOSE" = true ] && echo "Skipping $file (size: $file_size bytes > max: $max_bytes bytes)" >&2
            return 1
        fi
    fi
    
    # If include-types is specified, only process those types
    if [ -n "$INCLUDE_TYPES" ]; then
        for include_type in "${INCLUDE_TYPES_ARRAY[@]}"; do
            if [ "$extension" = "$include_type" ]; then
                return 0
            fi
        done
        return 1
    fi
    
    # Otherwise, check ignore-types
    for ignore_type in "${IGNORE_TYPES_ARRAY[@]}"; do
        if [ "$extension" = "$ignore_type" ]; then
            [ "$VERBOSE" = true ] && echo "Skipping $file (ignored extension: $extension)" >&2
            return 1
        fi
    done
    
    return 0
}

# Function to process a directory
process_directory() {
    local dir="$1"
    local real_path=$(realpath "$dir")
    
    # Check if we've already visited this directory (symbolic link protection)
    for visited in "${visited_dirs[@]}"; do
        if [ "$visited" = "$real_path" ]; then
            [ "$VERBOSE" = true ] && echo "Skipping already visited directory: $dir" >&2
            return
        fi
    done
    visited_dirs+=("$real_path")
    
    # Check if directory should be ignored
    local dir_basename=$(basename "$dir")
    for ignore_folder in "${IGNORE_FOLDERS_ARRAY[@]}"; do
        if [ "$dir_basename" = "$ignore_folder" ]; then
            [ "$VERBOSE" = true ] && echo "Skipping ignored folder: $dir" >&2
            return
        fi
    done
    
    # Process all entries in the directory
    for entry in "$dir"/*; do
        [ -e "$entry" ] || continue  # Skip if doesn't exist (empty directory)
        
        if [ -f "$entry" ]; then
            if should_process_file "$entry"; then
                # Make path relative to target directory for cleaner output
                local relative_path="${entry#$TARGET_DIR/}"
                processed_files+=("$relative_path")
                [ "$VERBOSE" = true ] && echo "Processing: $relative_path" >&2
            fi
        elif [ -d "$entry" ]; then
            process_directory "$entry"
        fi
    done
}

# Function to write file content with markdown formatting
write_file_content() {
    local file="$1"
    local full_path="$TARGET_DIR/$file"
    local language=$(get_language_from_extension "$full_path")
    
    echo "" >> "$OUTPUT_FILE"
    echo "## $file" >> "$OUTPUT_FILE"
    echo '```'"$language" >> "$OUTPUT_FILE"
    # Use cat to preserve file content exactly, handling special characters
    cat "$full_path" >> "$OUTPUT_FILE" 2>/dev/null || {
        echo "Error reading file: $full_path" >> "$OUTPUT_FILE"
    }
    echo "" >> "$OUTPUT_FILE"
    echo '```' >> "$OUTPUT_FILE"
}

# Main processing
main() {
    # Clear or create output file
    > "$OUTPUT_FILE"
    
    [ "$VERBOSE" = true ] && echo "Starting to process directory: $TARGET_DIR" >&2
    
    # Process the directory tree
    process_directory "$TARGET_DIR"
    
    # Sort the processed files for consistent output
    IFS=$'\n' sorted_files=($(sort <<<"${processed_files[*]}"))
    unset IFS
    
    # Generate table of contents if requested
    if [ "$NO_TOC" != true ] && [ ${#sorted_files[@]} -gt 0 ]; then
        echo "# Table of Contents" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE"
        for file in "${sorted_files[@]}"; do
            echo "- $file" >> "$OUTPUT_FILE"
        done
        echo "" >> "$OUTPUT_FILE"
        echo "---" >> "$OUTPUT_FILE"
    fi
    
    # Write all file contents
    for file in "${sorted_files[@]}"; do
        write_file_content "$file"
    done
    
    # Report results
    if [ "$VERBOSE" = true ]; then
        echo "" >&2
        echo "Processed ${#sorted_files[@]} files" >&2
        echo "Output written to: $OUTPUT_FILE" >&2
    fi
    
    # Check if any files were processed
    if [ ${#sorted_files[@]} -eq 0 ]; then
        echo "Warning: No files were processed. Check your filters and target directory." >&2
        return 1
    fi
    
    return 0
}

# Run main function
main