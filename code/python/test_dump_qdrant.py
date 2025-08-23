#!/usr/bin/env python3
"""
Test script to dump all conversations from Qdrant storage.
"""

import asyncio
import json
from datetime import datetime
from pprint import pprint

# Add the project root to path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import CONFIG
from storage_providers.qdrant_storage import QdrantStorageProvider


async def dump_qdrant_conversations():
    """Dump all conversations from Qdrant storage."""
    
    print("=" * 80)
    print("QDRANT CONVERSATION DATABASE DUMP")
    print("=" * 80)
    
    # Get storage configuration
    storage_config = CONFIG.conversation_storage
    print(f"\nStorage Type: {storage_config.type}")
    print(f"Collection Name: {storage_config.collection_name or 'nlweb_conversations'}")
    
    if storage_config.type != 'qdrant':
        print(f"\nWARNING: Storage type is '{storage_config.type}', not 'qdrant'")
        print("This script is specifically for Qdrant storage.")
        return
    
    # Initialize Qdrant storage provider
    print("\nInitializing Qdrant storage provider...")
    storage = QdrantStorageProvider(storage_config)
    await storage.initialize()
    
    # Get collection info
    try:
        collection_info = await storage.client.get_collection(storage.collection_name)
        print(f"\nCollection Info:")
        print(f"  Points count: {collection_info.points_count}")
        print(f"  Vectors size: {collection_info.config.params.vectors.size}")
    except Exception as e:
        print(f"Error getting collection info: {e}")
        return
    
    # Scroll through all points in the collection
    print("\n" + "=" * 80)
    print("ALL CONVERSATIONS:")
    print("=" * 80)
    
    try:
        # Get all points without any filter
        results = await storage.client.scroll(
            collection_name=storage.collection_name,
            limit=1000,  # Get up to 1000 conversations
            with_payload=True,
            with_vectors=False  # Don't include embeddings in output
        )
        
        points = results[0]
        
        if not points:
            print("\nNo conversations found in the database.")
            return
        
        print(f"\nFound {len(points)} conversation(s)\n")
        
        # Group by thread_id for better organization
        threads = {}
        for point in points:
            payload = point.payload
            thread_id = payload.get("thread_id", "unknown")
            
            if thread_id not in threads:
                threads[thread_id] = []
            
            threads[thread_id].append(payload)
        
        # Display conversations grouped by thread
        for thread_id, conversations in threads.items():
            print(f"\n{'=' * 60}")
            print(f"THREAD ID: {thread_id}")
            print(f"{'=' * 60}")
            
            # Sort conversations by time
            conversations.sort(key=lambda x: x.get("time_of_creation", ""))
            
            for i, conv in enumerate(conversations, 1):
                print(f"\n--- Conversation {i} ---")
                print(f"ID: {conv.get('conversation_id', 'N/A')}")
                print(f"User ID: {conv.get('user_id', 'N/A')}")
                print(f"Site: {conv.get('site', 'N/A')}")
                print(f"Time: {conv.get('time_of_creation', 'N/A')}")
                
                # Show user prompt (truncated if too long)
                user_prompt = conv.get('user_prompt', 'N/A')
                if len(user_prompt) > 200:
                    print(f"User Prompt: {user_prompt[:200]}...")
                else:
                    print(f"User Prompt: {user_prompt}")
                
                # Show response (truncated if too long)
                response = conv.get('response', 'N/A')
                if isinstance(response, str):
                    try:
                        # Try to parse as JSON and show item count
                        response_data = json.loads(response)
                        if isinstance(response_data, dict) and 'content' in response_data:
                            item_count = len(response_data['content'])
                            print(f"Response: JSON with {item_count} items")
                            # Show first item as sample
                            if item_count > 0:
                                first_item = response_data['content'][0]
                                print(f"  First item: {first_item.get('name', 'N/A')}")
                        else:
                            print(f"Response: {str(response)[:200]}...")
                    except:
                        if len(response) > 200:
                            print(f"Response: {response[:200]}...")
                        else:
                            print(f"Response: {response}")
                
                # Show summary if present
                if conv.get('summary'):
                    print(f"Summary: {conv.get('summary')}")
                if conv.get('main_topics'):
                    print(f"Main Topics: {', '.join(conv.get('main_topics', []))}")
                if conv.get('key_insights'):
                    print(f"Key Insights: {conv.get('key_insights')}")
        
        # Summary statistics
        print(f"\n{'=' * 80}")
        print("SUMMARY STATISTICS:")
        print(f"{'=' * 80}")
        print(f"Total Conversations: {len(points)}")
        print(f"Total Threads: {len(threads)}")
        
        # Count by user
        users = {}
        for point in points:
            user_id = point.payload.get("user_id", "unknown")
            users[user_id] = users.get(user_id, 0) + 1
        
        print(f"\nConversations by User:")
        for user_id, count in users.items():
            print(f"  {user_id}: {count} conversation(s)")
        
        # Count by site
        sites = {}
        for point in points:
            site = point.payload.get("site", "unknown")
            sites[site] = sites.get(site, 0) + 1
        
        print(f"\nConversations by Site:")
        for site, count in sites.items():
            print(f"  {site}: {count} conversation(s)")
            
    except Exception as e:
        print(f"\nError scrolling through conversations: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Close the client
        if storage.client:
            await storage.client.close()
            print("\n\nQdrant client closed.")


if __name__ == "__main__":
    print("Starting Qdrant conversation dump...")
    asyncio.run(dump_qdrant_conversations())
    print("\nDone!")