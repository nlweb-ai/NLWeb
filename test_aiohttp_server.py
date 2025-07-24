#!/usr/bin/env python3
"""Simple test to verify aiohttp server can start"""

import asyncio
import sys
import os

# Add the code/python directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code', 'python'))

async def test_server():
    """Test if the server can start"""
    try:
        from webserver.aiohttp_server import AioHTTPServer
        
        print("Creating server instance...")
        server = AioHTTPServer()
        
        print("Server created successfully!")
        print(f"Config: {server.config}")
        
        # Don't actually start the server, just test creation
        app = await server.create_app()
        print("App created successfully!")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_server())
    sys.exit(0 if success else 1)