#!/usr/bin/env python3
"""
Utility script to set logging levels for all modules.

Usage:
    python set_log_level.py DEBUG    # Set all loggers to DEBUG
    python set_log_level.py INFO     # Set all loggers to INFO
    python set_log_level.py WARNING  # Set all loggers to WARNING
    python set_log_level.py ERROR    # Set all loggers to ERROR
    python set_log_level.py CRITICAL # Set all loggers to CRITICAL
"""

import sys
import os
from logging_config_helper import get_logging_config


def print_usage():
    """Print usage information"""
    print("Usage: python set_log_level.py <LEVEL>")
    print("Where <LEVEL> is one of: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    print("\nExample:")
    print("  python set_log_level.py DEBUG")


def set_all_loggers(level: str):
    """Set all loggers to the specified level"""
    try:
        config = get_logging_config()
        config.set_all_loggers_level(level)
        
        # Get all environment variables
        env_vars = config.get_all_env_vars()
        
        print(f"\n✓ Successfully updated configuration to set all loggers to {level}")
        print("\nTo apply these changes, you have two options:")
        print("\n1. Set environment variables individually:")
        for env_var, _ in env_vars.items():
            print(f"   export {env_var}={level}")
        
        print("\n2. Or use this single command to set all at once:")
        all_exports = " && ".join([f"export {env_var}={level}" for env_var in env_vars.keys()])
        print(f"   {all_exports}")
        
        print("\n3. For Windows PowerShell, use:")
        for env_var in env_vars.keys():
            print(f'   $env:{env_var}="{level}"')
        
        print("\n4. For Windows Command Prompt, use:")
        for env_var in env_vars.keys():
            print(f'   set {env_var}={level}')
        
    except ValueError as e:
        print(f"Error: {e}")
        print("\nValid log levels are: DEBUG, INFO, WARNING, ERROR, CRITICAL")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def main():
    """Main entry point"""
    if len(sys.argv) != 2:
        print_usage()
        sys.exit(1)
    
    log_level = sys.argv[1].upper()
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    
    if log_level not in valid_levels:
        print(f"Error: Invalid log level '{log_level}'")
        print(f"Valid levels are: {', '.join(valid_levels)}")
        sys.exit(1)
    
    set_all_loggers(log_level)


if __name__ == "__main__":
    main()