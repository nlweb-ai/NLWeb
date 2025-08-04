#!/usr/bin/env python3
"""Debug script to trace participant corruption issue."""

import asyncio
import aiohttp
import json

async def test_create_conversation():
    """Test creating a conversation and immediately retrieving it."""
    
    # Create conversation
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
            print(f"Create response: {json.dumps(data, indent=2)}")
            
            if resp.status != 201:
                print(f"ERROR: Failed to create conversation")
                return
                
            conversation_id = data['conversation_id']
        
        # Immediately retrieve it
        print(f"\n=== Getting conversation {conversation_id} ===")
        async with session.get(
            f"http://localhost:8000/chat/conversations/{conversation_id}",
            headers=headers
        ) as resp:
            print(f"Get response status: {resp.status}")
            data = await resp.json()
            print(f"Get response: {json.dumps(data, indent=2)}")

if __name__ == "__main__":
    asyncio.run(test_create_conversation())