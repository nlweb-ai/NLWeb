#!/usr/bin/env python3
"""
Script to clear all conversations from Qdrant storage.
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import CONFIG
from storage_providers.qdrant_storage import QdrantStorageProvider


async def clear_qdrant_conversations():
    """Clear all conversations from Qdrant storage."""
    
    print("=" * 80)
    print("CLEARING QDRANT CONVERSATION DATABASE")
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
    
    # Get initial count
    try:
        collection_info = await storage.client.get_collection(storage.collection_name)
        initial_count = collection_info.points_count
        print(f"\nCurrent points count: {initial_count}")
        
        if initial_count == 0:
            print("Database is already empty.")
            return
            
    except Exception as e:
        print(f"Error getting collection info: {e}")
        return
    
    # Confirm before deletion
    print(f"\n⚠️  WARNING: This will delete ALL {initial_count} conversations!")
    response = input("Are you sure you want to continue? (yes/no): ")
    
    if response.lower() != 'yes':
        print("\nCancelled. No data was deleted.")
        return
    
    print("\nDeleting all conversations...")
    
    try:
        # Get all point IDs first
        print("Fetching all point IDs...")
        results = await storage.client.scroll(
            collection_name=storage.collection_name,
            limit=10000,  # Get all points
            with_payload=False,
            with_vectors=False
        )
        
        points = results[0]
        point_ids = [point.id for point in points]
        
        if point_ids:
            print(f"Deleting {len(point_ids)} points...")
            # Delete all points by their IDs
            await storage.client.delete(
                collection_name=storage.collection_name,
                points_selector=point_ids
            )
        
        # Verify deletion
        collection_info = await storage.client.get_collection(storage.collection_name)
        final_count = collection_info.points_count
        
        print(f"\n✅ Successfully cleared the database!")
        print(f"   Deleted: {initial_count} conversations")
        print(f"   Current count: {final_count}")
        
    except Exception as e:
        print(f"\n❌ Error clearing conversations: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Close the client
        if storage.client:
            await storage.client.close()
            print("\nQdrant client closed.")


if __name__ == "__main__":
    print("Starting Qdrant conversation database clearing...")
    asyncio.run(clear_qdrant_conversations())
    print("\nDone!")