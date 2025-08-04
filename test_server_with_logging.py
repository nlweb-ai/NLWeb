#!/usr/bin/env python3
"""Run server with detailed logging to debug participant issue."""

import sys
import os
import logging

# Configure logging FIRST
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True
)

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code/python'))

# Now import and run server
import asyncio
from webserver.aiohttp_server import run_server
from core.config import CONFIG

# Ensure all loggers are at INFO level
logging.getLogger().setLevel(logging.INFO)
logging.getLogger('chat').setLevel(logging.INFO)
logging.getLogger('chat_storage_providers').setLevel(logging.INFO)
logging.getLogger('webserver').setLevel(logging.INFO)

async def main():
    print("Starting server with debug logging...")
    await run_server(CONFIG, mode='development')

if __name__ == '__main__':
    asyncio.run(main())