#!/usr/bin/env bash

# color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
BOLD='\033[1m'
UNDERLINE='\033[4m'
NC='\033[0m' # No Color

# utility functions
function _debug(){
    local message="$1"
    
    if [ "$DEBUG" = true ]; then
        echo -e "  ${YELLOW}> $message${NC}"
    fi
}

function _debug_mask(){
    local label="$1"
    local message="$2"

    message="$(echo "$message" | sed -E 's/^.*/****&/; s/^(.*)(.{4})$/****\2/')"
    if [ "$DEBUG" = true ]; then
        _debug "$label $message"
    fi
}

function _success(){
    local message="$1"
    
    echo -e "  ${GREEN}> $message${NC}"
}

function _info(){
    local message="$1"
    
    echo -e "  ${CYAN}> $message${NC}"
}

function _warn(){
    local message="$1"
    
    echo -e "${RED}> $message${NC}"
}

# error is just an alias for warn, but introduced to improve readability
function _error(){
    local message="$1" 
    _warn "$message"
}

function _info_mask(){
    local label="$1"
    local message="$2"
    
    message="$(echo "$message" | sed -E 's/^.*/****&/; s/^(.*)(.{4})$/****\2/')"
    _info "$label $message"
}

function _prompt() {
  printf "\n\e[35m>%s\n\e[0m" "$@"
}