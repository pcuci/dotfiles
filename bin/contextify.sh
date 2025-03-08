#!/bin/env bash

# Check if a directory path is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <project_directory>"
    exit 1
fi

# Project directory path
project_dir="$1"

# Validate that the directory exists
if [ ! -d "$project_dir" ]; then
    echo "Error: Directory $project_dir does not exist."
    exit 1
fi

# Extract repository name from the directory
repo_name=$(basename "$project_dir")

# Output file
output_file="${repo_name}_context.md"

# Remove the output file if it already exists
rm -f "$output_file"

# Function to process each file
process_file() {
    local file="$1"
    local max_lines=35

    # Count the number of lines in the file
    line_count=$(wc -l <"$file")

    # Skip files with more than the defined number of lines
    if [ "$line_count" -gt "$max_lines" ]; then
        echo "Skipping large file: $file ($line_count lines)"
        return
    fi

    echo "Processing file: $file"
    echo "Path: $file" >>"$output_file"
    echo "" >>"$output_file"

    # Determine the file extension
    extension="${file##*.}"

    # Set the appropriate language for the code block
    case "$extension" in
    ts) language="typescript" ;;
    js) language="javascript" ;;
    jsx) language="javascript" ;;
    tsx) language="typescript" ;;
    vue) language="html" ;;
    html) language="html" ;;
    css) language="css" ;;
    scss) language="scss" ;;
    json) language="json" ;;
    md) language="" ;;
    *) language="plaintext" ;;
    esac

    echo "\`\`\`$language" >>"$output_file"
    cat "$file" >>"$output_file"
    echo "\`\`\`" >>"$output_file"
    echo "" >>"$output_file"
    echo "-----------" >>"$output_file"
    echo "" >>"$output_file"
}

# Check if required tools are installed
for tool in fdfind; do
    if ! command -v $tool &>/dev/null; then
        echo "Error: $tool is not installed. Please install $tool and try again."
        exit 1
    fi
done

# Change to the provided directory
cd "$project_dir"

# Find files using fdfind, include only paths with 'web-component' and 'vue', then process each file
fdfind -H -t f -e ts -e js -e tsx -e jsx -e vue -e html -e css -e scss -e json -e md |
    grep -E 'vue' |
    sort -n -t'/' -k'1' |
    while read -r file; do
        process_file "$file"
    done

# Move the output file to the original directory
mv "$output_file" "$OLDPWD"

# Change back to the original directory
cd "$OLDPWD"

echo "Project contents have been processed and combined into $output_file"
