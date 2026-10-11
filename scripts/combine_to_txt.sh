#!/usr/bin/env bash

# Arguments from main script
TARGET_DIR="$1"
OUTPUT_FILE="$2"
IGNORE_TYPES="$3"
IGNORE_FOLDERS="$4"
IGNORE_FILES="$5"
INCLUDE_TYPES="$6"
MAX_FILE_SIZE="$7"
NO_TOC="$8"
VERBOSE="$9"
FILES_FROM="${10:-}"   # a file listing the files to use, in order, or - for stdin
SUMMARY="${11:-}"      # one sentence saying what this is, at the top

# Track visited directories to prevent symbolic link recursion
declare -a visited_dirs=()
declare -a processed_files=()

# Convert comma-separated lists to arrays
IFS=',' read -ra IGNORE_TYPES_ARRAY <<< "$IGNORE_TYPES"
IFS=',' read -ra IGNORE_FOLDERS_ARRAY <<< "$IGNORE_FOLDERS"
if [ -n "$IGNORE_FILES" ]; then
    IFS=',' read -ra IGNORE_FILES_ARRAY <<< "$IGNORE_FILES"
fi
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
    
    # Check if file is in the ignore-files list
    if [ -n "$IGNORE_FILES" ]; then
        for ignore_file in "${IGNORE_FILES_ARRAY[@]}"; do
            if [ "$basename" = "$ignore_file" ]; then
                [ "$VERBOSE" = true ] && echo "Skipping $file (ignored file: $basename)" >&2
                return 1
            fi
        done
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
            # Never read our own output (it may live inside the target directory)
            if [ "$(realpath "$entry")" = "$OUTPUT_REAL" ]; then
                continue
            fi
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

# True if FILE has a NUL byte in its first 8 KB (images, archives, fonts)
is_binary() {
    local total kept
    total=$(head -c 8192 "$1" | wc -c)
    kept=$(head -c 8192 "$1" | tr -d '\000' | wc -c)
    [ "$total" -ne "$kept" ]
}

# Resolve a range spec ("12-14,3,40-") for a file of TOTAL lines into sorted, merged
# "start-end,start-end" in RESOLVED; prints the problem and returns 1 if it can't be printed.
resolve_ranges() {
    local spec="$1" total="$2" part start end pairs="" merged="" ms=0 me=0
    local IFS=','
    for part in $spec; do
        start="${part%%-*}"
        case "$part" in
            *-) end="$total" ;;
            *-*) end="${part#*-}" ;;
            *) end="$start" ;;
        esac
        if [ "$start" -lt 1 ]; then echo "line numbers start at 1"; return 1; fi
        if [ "$end" -lt "$start" ]; then echo "$start-$end ends before it starts"; return 1; fi
        if [ "$start" -gt "$total" ]; then
            echo "line $start starts after the end (the file has $total lines)"; return 1
        fi
        [ "$end" -gt "$total" ] && end="$total"
        pairs="$pairs$start $end"$'\n'
    done
    unset IFS
    while read -r start end; do
        [ -z "$start" ] && continue
        if [ "$me" -gt 0 ] && [ "$start" -le $((me + 1)) ]; then
            [ "$end" -gt "$me" ] && me="$end"
        else
            [ "$me" -gt 0 ] && merged="$merged,$ms-$me"
            ms="$start"; me="$end"
        fi
    done <<< "$(printf '%s' "$pairs" | sort -n -k1,1 -k2,2)"
    merged="$merged,$ms-$me"
    RESOLVED="${merged#,}"
}

# A list entry's suffix ("10-40,+12-14,-30") for a file of TOTAL lines: SHOWN (the lines to
# print, "" for the whole file), MARKED (resolved +ranges, also shown) and REMOVED (line numbers
# after which lines were removed). Every range is printed and +ranges are also marked; with no
# range at all, or ranges covering it all, the whole file is. Prints the problem and returns 1
# if it can't be printed.
resolve_spec() {
    local spec="$1" total="$2" part plain="" marks="" gone=""
    local IFS=','
    for part in $spec; do
        case "$part" in
            +*) marks="$marks,${part#+}" ;;
            -*) if [ "${part#-}" -gt "$total" ]; then
                    echo "$part: line ${part#-} is after the end (the file has $total lines)"; return 1
                fi
                gone="$gone,${part#-}" ;;
            *) plain="$plain,$part" ;;
        esac
    done
    unset IFS
    MARKED="" SHOWN=""
    if [ -n "$marks" ]; then
        resolve_ranges "${marks#,}" "$total" || return 1
        MARKED="$RESOLVED"
    fi
    if [ -n "$plain$MARKED" ]; then
        plain="${plain#,}"
        resolve_ranges "${plain}${plain:+${MARKED:+,}}$MARKED" "$total" || return 1
        SHOWN="$RESOLVED"
        [ -n "$MARKED$gone" ] && [ "$SHOWN" = "1-$total" ] && SHOWN=""  # all of it, with marks
    fi
    REMOVED="$(printf '%s\n' ${gone//,/ } | sort -n -u | paste -sd, -)"
}

# The heading note for an entry: "lines 12-13, 19; marked 12-13; lines removed after 30"
spec_label() {
    local shown="$1" marked="$2" removed="$3" out=""
    [ -n "$shown" ] && out="$(ranges_label "$shown")"
    [ -n "$marked" ] && out="${out:+$out; }marked $(ranges_label "$marked" | sed 's/^lines* //')"
    [ -n "$removed" ] && out="${out:+$out; }lines removed after ${removed//,/, }"
    echo "$out"
}

# "12-13,19-19" -> "lines 12-13, 19" (or "line 7")
ranges_label() {
    local spec="$1" part out="" count=0 single=""
    local IFS=','
    for part in $spec; do
        count=$((count + 1))
        if [ "${part%-*}" = "${part#*-}" ]; then part="${part%-*}"; single="$part"; fi
        out="$out, $part"
    done
    unset IFS
    if [ "$count" -eq 1 ] && [ -n "$single" ]; then echo "line $single"; else echo "lines ${out#, }"; fi
}

# Ranges of SPEC ("367-391,400-410") in FILE that stop inside an indented block, one
# "start end last" per line: the lines after END indented deeper than the range's first line,
# plus a closing } ) ] or `end` at that line's indent, belong to the same block (as code2pdf).
cut_blocks() {
    awk -v spec="$2" '
        function indent(s,    i, c, n) {
            n = 0
            for (i = 1; i <= length(s); i++) {
                c = substr(s, i, 1)
                if (c == " ") n++
                else if (c == "\t") n += 8 - n % 8
                else break
            }
            return n
        }
        { line[NR] = $0 }
        END {
            count = split(spec, parts, ",")
            for (k = 1; k <= count; k++) {
                split(parts[k], se, "-"); start = se[1] + 0; end = se[2] + 0
                base = -1
                for (n = start; n <= end; n++) if (line[n] ~ /[^ \t]/) { base = indent(line[n]); break }
                if (base < 0) continue
                last = end
                for (n = end + 1; n <= NR; n++) {
                    if (line[n] !~ /[^ \t]/) continue
                    if (indent(line[n]) > base) { last = n; continue }
                    rest = line[n]; sub(/^[ \t]+/, "", rest)
                    if (indent(line[n]) == base && rest ~ /^([\])}]|end([^A-Za-z0-9_]|$))/) last = n
                    break
                }
                if (last > end) print start, end, last
            }
        }' "$1"
}

# --files-from: exactly the listed files, in the listed order. Paths are relative to TARGET_DIR
# (or to the current folder), or absolute; they must be inside TARGET_DIR. Binary files are
# skipped; missing files are errors. Sets sorted_files.
read_file_list() {
    local source="$1" line path real rel seen=$'\n'
    local -a problems=() binaries=()
    local target_real
    target_real="$(cd "$TARGET_DIR" && pwd -P)"
    sorted_files=()
    file_ranges=()
    file_marked=()
    file_removed=()
    cut_warnings=()
    local spec base note
    if [ "$source" = "-" ]; then
        exec 3<&0
    elif ! exec 3<"$source"; then
        echo "Error: cannot read --files-from $source" >&2
        return 1
    fi
    while IFS= read -r line <&3 || [ -n "$line" ]; do
        line="${line%$'\r'}"
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        [ -z "$line" ] && continue
        case "$line" in
            /*) path="$line" ;;
            *) path="$TARGET_DIR/$line"
               if [ ! -e "$path" ] && [ -e "$line" ]; then path="$PWD/$line"; fi ;;
        esac
        spec="" MARKED="" REMOVED=""
        # FILE:START-END[,START-END] prints part of a file, +START-END marks lines, -N says lines
        # were removed after line N (a name that is a file stays whole)
        if [ ! -f "$path" ] && [[ "$line" =~ ^(.+):((\+?[0-9]+(-[0-9]*)?|-[0-9]+)(,(\+?[0-9]+(-[0-9]*)?|-[0-9]+))*)$ ]]; then
            base="${BASH_REMATCH[1]}"
            spec="${BASH_REMATCH[2]}"
            case "$base" in
                /*) path="$base" ;;
                *) path="$TARGET_DIR/$base"
                   if [ ! -e "$path" ] && [ -e "$base" ]; then path="$PWD/$base"; fi ;;
            esac
            if [ -f "$path" ]; then
                if ! note=$(resolve_spec "$spec" "$(awk 'END { print NR }' "$path")"); then
                    problems+=("$line: $note")
                    continue
                fi
                resolve_spec "$spec" "$(awk 'END { print NR }' "$path")"
                spec="$SHOWN"
            fi
        fi
        if [ ! -f "$path" ]; then
            problems+=("not a file: $line")
            continue
        fi
        real="$(cd "$(dirname "$path")" && pwd -P)/$(basename "$path")"
        case "$real" in
            "$target_real"/*) rel="${real#"$target_real"/}" ;;
            *) problems+=("outside $TARGET_DIR: $line"); continue ;;
        esac
        case "$seen" in *$'\n'"$rel:$spec|$MARKED|$REMOVED"$'\n'*) continue ;; esac
        seen="$seen$rel:$spec|$MARKED|$REMOVED"$'\n'
        [ "$real" = "$OUTPUT_REAL" ] && continue
        if is_binary "$path"; then
            binaries+=("$rel")
            continue
        fi
        sorted_files+=("$rel")
        file_ranges+=("$spec")
        file_marked+=("$MARKED")
        file_removed+=("$REMOVED")
        if [ -n "$spec" ] && [ -z "$MARKED$REMOVED" ]; then  # marked pieces are cut on purpose
            local cut_start cut_end cut_last
            while read -r cut_start cut_end cut_last; do
                [ -z "$cut_start" ] && continue
                cut_warnings+=("Warning: $rel:$cut_start-$cut_end stops inside a block that goes on to line $cut_last; to print it whole, use $rel:$(printf '%s' ",$spec," | sed "s/,$cut_start-$cut_end,/,$cut_start-$cut_last,/; s/^,//; s/,\$//")")
            done <<< "$(cut_blocks "$path" "$spec")"
        fi
    done
    exec 3<&-
    if [ ${#binaries[@]} -gt 0 ]; then
        local shown="${binaries[0]}" i
        for ((i = 1; i < ${#binaries[@]} && i < 3; i++)); do shown="$shown, ${binaries[$i]}"; done
        [ ${#binaries[@]} -gt 3 ] && shown="$shown, …"
        local noun="files"
        [ ${#binaries[@]} -eq 1 ] && noun="file"
        echo "Skipped ${#binaries[@]} binary $noun: $shown" >&2
    fi
    if [ ${#problems[@]} -gt 0 ]; then
        local p
        for p in "${problems[@]}"; do echo "Error: --files-from: $p" >&2; done
        return 1
    fi
}

# Function to write file content with markdown formatting
write_file_content() {
    local file="$1" spec="${2:-}" marked="${3:-}" removed="${4:-}"
    local full_path="$TARGET_DIR/$file"
    local language=$(get_language_from_extension "$full_path")
    local label
    label="$(spec_label "$spec" "$marked" "$removed")"
    
    echo "" >> "$OUTPUT_FILE"
    if [ -n "$label" ]; then
        echo "## $file ($label)" >> "$OUTPUT_FILE"
    else
        echo "## $file" >> "$OUTPUT_FILE"
    fi
    echo '```'"$language" >> "$OUTPUT_FILE"
    if [ -n "$removed" ]; then
        # Lines removed after line N get a marker line; gaps between ranges as below
        awk -v shown="$spec" -v removed="$removed" '
            BEGIN {
                n = split(shown, parts, ",")
                for (i = 1; i <= n; i++) { split(parts[i], se, "-"); s[i] = se[1] + 0; e[i] = se[2] + 0 }
                m = split(removed, rm, ",")
                for (i = 1; i <= m; i++) gone[rm[i] + 0] = 1
                if (gone[0] && (n == 0 || s[1] == 1)) print "... (lines removed here)"
            }
            {
                k = 0
                if (n == 0) k = 1
                else for (i = 1; i <= n; i++) if (NR >= s[i] && NR <= e[i]) { k = i; break }
                if (!k) next
                if (n > 0 && k > 1 && NR == s[k]) {
                    if (e[k - 1] + 1 == s[k] - 1) print "... (line " e[k - 1] + 1 " not shown)"
                    else print "... (lines " e[k - 1] + 1 "-" s[k] - 1 " not shown)"
                }
                print
                if (gone[NR]) print "... (lines removed here)"
            }' "$full_path" >> "$OUTPUT_FILE"
    elif [ -n "$spec" ]; then
        # Only these lines; a marker between ranges says what is left out
        local part start end previous=0
        local IFS=','
        for part in $spec; do
            start="${part%-*}"; end="${part#*-}"
            if [ "$previous" -gt 0 ]; then
                if [ $((previous + 1)) -eq $((start - 1)) ]; then
                    echo "... (line $((previous + 1)) not shown)" >> "$OUTPUT_FILE"
                else
                    echo "... (lines $((previous + 1))-$((start - 1)) not shown)" >> "$OUTPUT_FILE"
                fi
            fi
            sed -n "${start},${end}p" "$full_path" >> "$OUTPUT_FILE"
            previous="$end"
        done
        unset IFS
    else
        # Use cat to preserve file content exactly, handling special characters
        cat "$full_path" >> "$OUTPUT_FILE" 2>/dev/null || {
            echo "Error reading file: $full_path" >> "$OUTPUT_FILE"
        }
    fi
    echo "" >> "$OUTPUT_FILE"
    echo '```' >> "$OUTPUT_FILE"
}

# Main processing
main() {
    # Clear or create output file
    > "$OUTPUT_FILE"
    OUTPUT_REAL=$(realpath "$OUTPUT_FILE")
    
    [ "$VERBOSE" = true ] && echo "Starting to process directory: $TARGET_DIR" >&2
    
    if [ -n "$FILES_FROM" ]; then
        read_file_list "$FILES_FROM" || return 1
    else
        # Process the directory tree
        process_directory "$TARGET_DIR"

        # Sort the processed files for consistent output
        IFS=$'\n' sorted_files=($(sort <<<"${processed_files[*]}"))
        unset IFS
    fi
    
    if [ -n "$SUMMARY" ]; then
        printf '# Summary\n\n%s\n\n' "$SUMMARY" >> "$OUTPUT_FILE"
    fi

    # Generate table of contents if requested
    if [ "$NO_TOC" != true ] && [ ${#sorted_files[@]} -gt 0 ]; then
        echo "# Table of Contents" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE"
        local i
        local label
        for ((i = 0; i < ${#sorted_files[@]}; i++)); do
            label="$(spec_label "${file_ranges[$i]:-}" "${file_marked[$i]:-}" "${file_removed[$i]:-}")"
            if [ -n "$label" ]; then
                echo "- ${sorted_files[$i]} ($label)" >> "$OUTPUT_FILE"
            else
                echo "- ${sorted_files[$i]}" >> "$OUTPUT_FILE"
            fi
        done
        echo "" >> "$OUTPUT_FILE"
        echo "---" >> "$OUTPUT_FILE"
    fi
    
    # Write all file contents
    local k
    for ((k = 0; k < ${#sorted_files[@]}; k++)); do
        write_file_content "${sorted_files[$k]}" "${file_ranges[$k]:-}" "${file_marked[$k]:-}" "${file_removed[$k]:-}"
    done
    
    # Report results
    if [ "$VERBOSE" = true ]; then
        echo "" >&2
        echo "Processed ${#sorted_files[@]} files" >&2
        echo "Output written to: $OUTPUT_FILE" >&2
    fi
    
    local warning
    for warning in ${cut_warnings[@]+"${cut_warnings[@]}"}; do echo "$warning" >&2; done

    # Check if any files were processed
    if [ ${#sorted_files[@]} -eq 0 ]; then
        echo "Warning: No files were processed. Check your filters and target directory." >&2
        return 1
    fi
    
    return 0
}

# Run main function
main