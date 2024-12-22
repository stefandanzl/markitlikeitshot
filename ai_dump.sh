#!/bin/bash

# ai_dump.sh
# Creates a comprehensive markdown file of the project structure and contents

# Default values
OUTPUT_FILE="ai_dump.md"
INCLUDE_TESTS=false
INCLUDE_DOCS=false
EXCLUDE_PATTERNS="__pycache__|*.pyc"
MAX_FILE_SIZE="2M"
VERBOSE=false

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function to display usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  -o, --output FILE     Specify output file (default: ai_dump.md)"
    echo "  -t, --include-tests   Include test files in the output"
    echo "  -d, --include-docs    Include documentation files (*.md, *.rst)"
    echo "  -e, --exclude PATH    Additional patterns to exclude (comma-separated)"
    echo "  -m, --max-size SIZE   Maximum file size to include (default: 1M)"
    echo "  -v, --verbose         Show verbose output"
    echo "  -h, --help           Display this help message"
    echo
    echo "Examples:"
    echo "  $0 --output custom.md --include-tests"
    echo "  $0 --exclude '*.log,*.tmp' --max-size 2M"
}

# Function to get file size in bytes (cross-platform)
get_file_size() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        stat -f%z "$1"
    else
        # Linux
        stat -c%s "$1"
    fi
}

# Function to convert human-readable size to bytes (e.g., "1M" to bytes)
to_bytes() {
    local size=$1
    local unit="${size: -1}"
    local number="${size::-1}"
    
    case "$unit" in
        K|k) echo $((number * 1024)) ;;
        M|m) echo $((number * 1024 * 1024)) ;;
        G|g) echo $((number * 1024 * 1024 * 1024)) ;;
        *) echo "$size" ;;  # Assume bytes if no unit
    esac
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -t|--include-tests)
            INCLUDE_TESTS=true
            shift
            ;;
        -d|--include-docs)
            INCLUDE_DOCS=true
            shift
            ;;
        -e|--exclude)
            EXCLUDE_PATTERNS="${EXCLUDE_PATTERNS}|$2"
            shift 2
            ;;
        -m|--max-size)
            MAX_FILE_SIZE="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Function to log verbose messages
log() {
    if [ "$VERBOSE" = true ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    fi
}

# Ensure output directory exists
OUTPUT_DIR=$(dirname "$OUTPUT_FILE")
mkdir -p "$OUTPUT_DIR"

log "Starting documentation generation..."

{
    echo -e "### Project Structure\n\n\`\`\`"
    if [ "$INCLUDE_TESTS" = true ]; then
        log "Including test files in tree output"
        tree "${SCRIPT_DIR}" -I "${EXCLUDE_PATTERNS}"
    else
        tree "${SCRIPT_DIR}" -I "${EXCLUDE_PATTERNS}|test_*"
    fi
    echo -e "\`\`\`\n\n### Configuration Files"
    
    # Core configuration files
    for file in "run.sh" "docker-compose.yml" "markitdown-service/Dockerfile" "markitdown-service/requirements.txt" "markitdown-service/pytest.ini"; do
        if [ -f "${SCRIPT_DIR}/${file}" ]; then
            # Check file size
            if [ $(get_file_size "${SCRIPT_DIR}/${file}") -lt $(to_bytes "${MAX_FILE_SIZE}") ]; then
                log "Processing file: ${file}"
                ext="${file##*.}"
                echo -e "\n\n### File: ${SCRIPT_DIR}/${file}\n\n\`\`\`${ext}"
                cat "${SCRIPT_DIR}/${file}"
                echo -e "\`\`\`"
            else
                log "Skipping large file: ${file}"
                echo -e "\n\n### File: ${SCRIPT_DIR}/${file}\n\nFile exceeds size limit of ${MAX_FILE_SIZE}"
            fi
        else
            log "Warning: File not found: ${file}"
        fi
    done
    
    # Documentation files if requested
    if [ "$INCLUDE_DOCS" = true ]; then
        log "Processing documentation files"
        echo -e "\n\n### Documentation Files"
        find "${SCRIPT_DIR}" -type f \( -name "*.md" -o -name "*.rst" \) -not -path "*/\.*" | while read file; do
            if [ $(get_file_size "$file") -lt $(to_bytes "${MAX_FILE_SIZE}") ]; then
                echo -e "\n\n### File: $file\n\n\`\`\`markdown"
                cat "$file"
                echo -e "\`\`\`"
            fi
        done
    fi
    
    # Python files
    log "Processing Python files"
    echo -e "\n\n### Python Files"
    find "${SCRIPT_DIR}/markitdown-service/app" -name "*.py" -type f -not -path "*/\.*" -not -path "*/__pycache__/*" | while read file; do
        if [ $(get_file_size "$file") -lt $(to_bytes "${MAX_FILE_SIZE}") ]; then
            log "Processing Python file: ${file}"
            echo -e "\n\n### File: $file\n\n\`\`\`python"
            cat "$file"
            echo -e "\`\`\`"
        else
            log "Skipping large Python file: ${file}"
            echo -e "\n\n### File: $file\n\nFile exceeds size limit of ${MAX_FILE_SIZE}"
        fi
    done
} > "${OUTPUT_FILE}"

log "Documentation generation complete"
echo "Project documentation has been generated in: ${OUTPUT_FILE}"