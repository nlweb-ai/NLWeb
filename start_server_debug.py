#!/usr/bin/env python3
"""Start server with debug output visible."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code/python'))

import asyncio
from aiohttp import web
from webserver.aiohttp_server import AioHttpServer
from core.config import CONFIG

async def main():
    """Run server with debug output."""
    print("Starting server with debug output...")
    server = AioHttpServer(CONFIG)
    try:
        await server.start()
        # Keep server running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        await server.stop()

if __name__ == '__main__':
    asyncio.run(main())