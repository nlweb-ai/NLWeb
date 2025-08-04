#!/usr/bin/env python3
"""Focused test to debug participant corruption."""

import asyncio
import aiohttp
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code/python'))

async def test_corruption():
    """Test to reproduce the corruption issue."""
    
    async with aiohttp.ClientSession() as session:
        # Create conversation
        print("\n=== Creating conversation ===")
        create_data = {
            "title": "Debug Test",
            "participants": [
                {"user_id": "test_user", "name": "Test User"}
            ],
            "enable_ai": False
        }
        
        headers = {"Authorization": "Bearer e2e_test_user"}
        
        async with session.post(
            "http://localhost:8000/chat/create",
            json=create_data,
            headers=headers
        ) as resp:
            print(f"Create response status: {resp.status}")
            data = await resp.json()
            
            if resp.status != 201:
                print(f"ERROR: Failed to create conversation: {data}")
                return
                
            conversation_id = data['conversation_id']
            print(f"Created conversation: {conversation_id}")
            
            # Check participants in response
            print(f"Participants in create response: {data.get('participants', [])}")
        
        # Wait a moment
        await asyncio.sleep(0.5)
        
        # Retrieve conversation
        print(f"\n=== Getting conversation {conversation_id} ===")
        async with session.get(
            f"http://localhost:8000/chat/conversations/{conversation_id}",
            headers=headers
        ) as resp:
            print(f"Get response status: {resp.status}")
            
            if resp.status == 200:
                data = await resp.json()
                print(f"Participants in get response: {data.get('participants', [])}")
            else:
                error_text = await resp.text()
                print(f"ERROR: {error_text}")

if __name__ == "__main__":
    # Start the corruption test
    asyncio.run(test_corruption())