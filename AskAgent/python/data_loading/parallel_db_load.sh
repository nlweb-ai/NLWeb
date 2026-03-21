#!/bin/bash

# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

# Script to load multiple files into the database in parallel
# Each file is loaded with its filename (minus .txt extension) as the site name
# Maximum 3 concurrent loads at any time

set -e

# Default values
MAX_JOBS=3
PYTHON_CMD=${PYTHON_CMD:-python}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to show usage
usage() {
    echo "Usage: $0 [OPTIONS] DIRECTORY"
    echo ""
    echo "Load all .txt files from DIRECTORY into the database in parallel"
    echo "Each file is loaded with its filename (minus .txt) as the site name"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -j, --jobs NUM          Maximum parallel jobs (default: 3)"
    echo "  -p, --python PYTHON     Python command to use (default: python)"
    echo "  -d, --db DB             Database/retrieval backend (default: from config)"
    echo "  -v, --verbose           Enable verbose output"
    echo ""
    echo "Examples:"
    echo "  $0 /path/to/data              # Load all .txt files from directory"
    echo "  $0 -j 5 /path/to/data         # Use 5 parallel jobs"
    echo "  $0 -d qdrant /path/to/data    # Load to specific database"
}

# Parse command line arguments
VERBOSE=false
DB_ARG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        -j|--jobs)
            MAX_JOBS="$2"
            shift 2
            ;;
        -p|--python)
            PYTHON_CMD="$2"
            shift 2
            ;;
        -d|--db)
            DB_ARG="--database $2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -*)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
        *)
            # This is the directory argument
            DIRECTORY="$1"
            shift
            ;;
    esac
done

# Check if directory was provided
if [ -z "$DIRECTORY" ]; then
    echo -e "${RED}Error: Directory argument is required${NC}"
    usage
    exit 1
fi

# Check if directory exists
if [ ! -d "$DIRECTORY" ]; then
    echo -e "${RED}Error: Directory does not exist: $DIRECTORY${NC}"
    exit 1
fi

# Check if Python is available
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo -e "${RED}Error: Python not found at: $PYTHON_CMD${NC}"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# We need to run from the code directory for Python imports to work
CODE_DIR="$(dirname "$SCRIPT_DIR")"
cd "$CODE_DIR"

echo -e "${GREEN}Working from: $CODE_DIR${NC}"

# Find all .txt files in the directory
TXT_FILES=($(find "$DIRECTORY" -maxdepth 1 -name "*.txt" -type f | sort))

if [ ${#TXT_FILES[@]} -eq 0 ]; then
    echo -e "${YELLOW}Warning: No .txt files found in $DIRECTORY${NC}"
    exit 0
fi

echo -e "${GREEN}Found ${#TXT_FILES[@]} .txt files to process${NC}"
echo "Using up to $MAX_JOBS parallel jobs"
echo ""

# Create temporary directory for job tracking
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Sort files by size (smallest first)
TXT_FILES_SORTED=($(ls -Sr "${TXT_FILES[@]}" 2>/dev/null))
TOTAL_FILES=${#TXT_FILES_SORTED[@]}

# Load the smallest file first as a test
if [ ${TOTAL_FILES} -gt 0 ]; then
    SMALLEST_FILE="${TXT_FILES_SORTED[0]}"
    SMALLEST_NAME=$(basename "$SMALLEST_FILE")
    SMALLEST_SIZE=$(ls -lh "$SMALLEST_FILE" | awk '{print $5}')
    
    echo -e "${GREEN}Loading smallest file first as a test:${NC}"
    echo -e "  File: $SMALLEST_NAME (size: $SMALLEST_SIZE)"
    echo ""
    
    # Load the smallest file
    site_name="${SMALLEST_NAME%.txt}"
    CMD="$PYTHON_CMD -m data_loading.db_load"
    if [ ! -z "$DB_ARG" ]; then
        CMD="$CMD $DB_ARG"
    fi
    CMD="$CMD \"$SMALLEST_FILE\" \"$site_name\""
    
    echo -e "${YELLOW}[TEST]${NC} Loading $SMALLEST_NAME as site '$site_name'"
    if [ "$VERBOSE" = true ]; then
        echo -e "${YELLOW}[CMD]${NC} $CMD"
    fi
    
    # Run the test load
    if eval $CMD; then
        echo -e "${GREEN}[SUCCESS]${NC} Test file loaded successfully!"
    else
        echo -e "${RED}[FAILED]${NC} Test file failed to load."
        echo -e "${RED}Error: There was a problem loading the test file. Please check your configuration and data format.${NC}"
        exit 1
    fi
    
    # Ask user whether to continue
    echo ""
    REMAINING_FILES=$((TOTAL_FILES - 1))
    echo -e "${YELLOW}Test load completed. Do you want to proceed with loading the remaining ${REMAINING_FILES} files? (y/N)${NC}"
    read -r response
    
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Aborting. No additional files were loaded.${NC}"
        exit 0
    fi
    
    echo ""
    echo -e "${GREEN}Proceeding with parallel load of remaining files...${NC}"
    echo ""
fi

# Process remaining files in parallel
CURRENT=0

for file_path in "${TXT_FILES_SORTED[@]}"; do
    # Skip the first file since we already loaded it
    if [ "$file_path" = "$SMALLEST_FILE" ]; then
        continue
    fi
    # Wait for a job slot to become available
    while [ $(ls -1 "$TEMP_DIR" | wc -l) -ge $MAX_JOBS ]; do
        # Check for completed jobs
        for job_file in "$TEMP_DIR"/*; do
            if [ -f "$job_file" ]; then
                # Check if the PID is still running
                pid=$(basename "$job_file")
                if ! kill -0 $pid 2>/dev/null; then
                    # Job completed, check exit status
                    wait $pid
                    exit_code=$?
                    job_info=$(cat "$job_file")
                    rm -f "$job_file"
                    
                    if [ $exit_code -eq 0 ]; then
                        echo -e "${GREEN}[DONE]${NC} $job_info"
                    else
                        echo -e "${RED}[FAIL]${NC} $job_info (exit code: $exit_code)"
                    fi
                fi
            fi
        done
        sleep 0.1
    done
    
    # Start new job
    CURRENT=$((CURRENT + 1))
    filename=$(basename "$file_path")
    site_name="${filename%.txt}"
    
    echo -e "${YELLOW}[START $CURRENT/$TOTAL_FILES]${NC} Loading $filename as site '$site_name'"
    
    # Run the Python command in background
    (
        # db_load.py expects: db_load.py [options] file_path site
        # Build the command with correct argument order
        CMD="$PYTHON_CMD -m data_loading.db_load"
        
        # Add database option if specified
        if [ ! -z "$DB_ARG" ]; then
            CMD="$CMD $DB_ARG"
        fi
        
        # Add the positional arguments
        CMD="$CMD \"$file_path\" \"$site_name\""
        
        # Show the command being run in verbose mode
        if [ "$VERBOSE" = true ]; then
            echo -e "${YELLOW}[CMD]${NC} $CMD"
            eval $CMD
        else
            eval $CMD >/dev/null 2>&1
        fi
    ) &
    
    # Save job info
    pid=$!
    echo "Loaded $filename as site '$site_name'" > "$TEMP_DIR/$pid"
done

# Wait for all remaining jobs to complete
echo ""
echo "Waiting for remaining jobs to complete..."

while [ $(ls -1 "$TEMP_DIR" 2>/dev/null | wc -l) -gt 0 ]; do
    for job_file in "$TEMP_DIR"/*; do
        if [ -f "$job_file" ]; then
            pid=$(basename "$job_file")
            if ! kill -0 $pid 2>/dev/null; then
                # Job completed
                wait $pid
                exit_code=$?
                job_info=$(cat "$job_file")
                rm -f "$job_file"
                
                if [ $exit_code -eq 0 ]; then
                    echo -e "${GREEN}[DONE]${NC} $job_info"
                else
                    echo -e "${RED}[FAIL]${NC} $job_info (exit code: $exit_code)"
                fi
            fi
        fi
    done
    sleep 0.1
done

echo ""
echo "======================================="
echo -e "${GREEN}All files processed!${NC}"
echo "======================================="