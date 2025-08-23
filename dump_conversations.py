#!/usr/bin/env python3
"""Script to dump all conversations from the storage backend."""

import asyncio
import sys
import os

# Add the code/python directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code', 'python'))

from core.conversation_history import get_storage_client

async def dump_conversations():
    """Dump all conversations from storage."""
    try:
        print("Getting storage client...")
        client = await get_storage_client()
        print(f"Storage client type: {type(client)}")
        
        # Try to get all conversations
        # Most storage providers have a method to list all or search without filters
        if hasattr(client, 'get_all_conversations'):
            print("\nFetching all conversations using get_all_conversations...")
            conversations = await client.get_all_conversations()
        elif hasattr(client, 'search_conversations'):
            print("\nFetching conversations using search_conversations with empty query...")
            # Try searching with empty query to get all
            conversations = await client.search_conversations(
                query="",
                user_id=None,
                site=None,
                limit=1000
            )
        else:
            print("Storage client doesn't have a method to retrieve all conversations")
            print(f"Available methods: {[m for m in dir(client) if not m.startswith('_')]}")
            return
        
        if not conversations:
            print("\nNo conversations found in storage")
            return
            
        print(f"\nFound {len(conversations)} conversations:")
        print("=" * 80)
        
        for i, conv in enumerate(conversations, 1):
            print(f"\nConversation {i}:")
            print("-" * 40)
            
            # Handle both dict and object responses
            if hasattr(conv, '__dict__'):
                conv_data = conv.__dict__
            else:
                conv_data = conv
                
            for key, value in conv_data.items():
                if key == 'response' and isinstance(value, str) and len(value) > 200:
                    print(f"  {key}: {value[:200]}...")
                elif key == 'embedding' and value:
                    print(f"  {key}: [vector of length {len(value) if hasattr(value, '__len__') else 'unknown'}]")
                else:
                    print(f"  {key}: {value}")
        
        print("\n" + "=" * 80)
        print(f"Total conversations: {len(conversations)}")
        
        # Also try to get unique users
        users = set()
        for conv in conversations:
            if hasattr(conv, 'user_id'):
                users.add(conv.user_id)
            elif isinstance(conv, dict) and 'user_id' in conv:
                users.add(conv['user_id'])
        
        if users:
            print(f"Unique users: {users}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(dump_conversations())