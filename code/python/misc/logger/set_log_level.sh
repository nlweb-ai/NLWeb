#!/bin/bash

# Shell script to set all logging levels
# Usage: source set_log_level.sh DEBUG

if [ "$#" -ne 1 ]; then
    echo "Usage: source set_log_level.sh <LEVEL>"
    echo "Where <LEVEL> is one of: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    echo ""
    echo "Note: You must use 'source' to run this script so environment variables are set in your current shell"
    exit 1
fi

LEVEL=$(echo "$1" | tr '[:lower:]' '[:upper:]')

# Validate log level
case $LEVEL in
    DEBUG|INFO|WARNING|ERROR|CRITICAL)
        ;;
    *)
        echo "Error: Invalid log level '$LEVEL'"
        echo "Valid levels are: DEBUG, INFO, WARNING, ERROR, CRITICAL"
        exit 1
        ;;
esac

# Set all environment variables
export LLM_LOG_LEVEL=$LEVEL
export AZURE_OPENAI_LOG_LEVEL=$LEVEL
export NLWEB_HANDLER_LOG_LEVEL=$LEVEL
export RANKING_LOG_LEVEL=$LEVEL
export FASTTRACK_LOG_LEVEL=$LEVEL
export PROMPT_RUNNER_LOG_LEVEL=$LEVEL
export PROMPTS_LOG_LEVEL=$LEVEL

echo "✓ Set all logging levels to $LEVEL"
echo ""
echo "Current logging environment variables:"
echo "  LLM_LOG_LEVEL=$LLM_LOG_LEVEL"
echo "  AZURE_OPENAI_LOG_LEVEL=$AZURE_OPENAI_LOG_LEVEL"
echo "  NLWEB_HANDLER_LOG_LEVEL=$NLWEB_HANDLER_LOG_LEVEL"
echo "  RANKING_LOG_LEVEL=$RANKING_LOG_LEVEL"
echo "  FASTTRACK_LOG_LEVEL=$FASTTRACK_LOG_LEVEL"
echo "  PROMPT_RUNNER_LOG_LEVEL=$PROMPT_RUNNER_LOG_LEVEL"
echo "  PROMPTS_LOG_LEVEL=$PROMPTS_LOG_LEVEL"