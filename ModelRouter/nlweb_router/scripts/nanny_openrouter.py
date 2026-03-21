#!/usr/bin/env python3
"""
Nanny script for score_openrouter.py

Monitors the OpenRouter scoring process and restarts it if it stops.
Run this script in the background to ensure continuous scoring.

Usage:
    python nanny_openrouter.py [--check-interval SECONDS] [--max-restarts COUNT]
"""

import subprocess
import time
import sys
import os
import argparse
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCORE_SCRIPT = os.path.join(SCRIPT_DIR, "score_openrouter.py")

def is_process_running():
    """Check if score_openrouter.py is currently running."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "score_openrouter.py"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[{timestamp()}] Error checking process: {e}")
        return False

def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def start_process():
    """Start score_openrouter.py as a background process."""
    print(f"[{timestamp()}] Starting score_openrouter.py...")
    try:
        process = subprocess.Popen(
            [sys.executable, SCORE_SCRIPT],
            cwd=os.path.dirname(SCRIPT_DIR),  # Run from nlweb_router directory
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True  # Detach from this process
        )
        print(f"[{timestamp()}] Started with PID {process.pid}")
        return process
    except Exception as e:
        print(f"[{timestamp()}] Failed to start: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Nanny script for score_openrouter.py")
    parser.add_argument(
        "--check-interval",
        type=int,
        default=60,
        help="Seconds between checks (default: 60)"
    )
    parser.add_argument(
        "--max-restarts",
        type=int,
        default=0,
        help="Maximum restarts before giving up (0 = unlimited, default: 0)"
    )
    args = parser.parse_args()

    print(f"[{timestamp()}] Nanny starting")
    print(f"[{timestamp()}] Check interval: {args.check_interval}s")
    print(f"[{timestamp()}] Max restarts: {'unlimited' if args.max_restarts == 0 else args.max_restarts}")

    restart_count = 0

    while True:
        if not is_process_running():
            if args.max_restarts > 0 and restart_count >= args.max_restarts:
                print(f"[{timestamp()}] Max restarts ({args.max_restarts}) reached. Exiting.")
                sys.exit(1)

            print(f"[{timestamp()}] Process not running. Restarting... (restart #{restart_count + 1})")
            process = start_process()
            if process:
                restart_count += 1
                # Give it a moment to start
                time.sleep(5)
                if is_process_running():
                    print(f"[{timestamp()}] Process started successfully")
                else:
                    print(f"[{timestamp()}] Process failed to start")
        else:
            # Reset restart count on successful run detection
            if restart_count > 0:
                print(f"[{timestamp()}] Process running. Restart count reset.")
                restart_count = 0

        time.sleep(args.check_interval)

if __name__ == "__main__":
    main()
