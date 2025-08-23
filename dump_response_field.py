#!/usr/bin/env python3
"""
Script to dump the response field from a conversation in the database
"""

import asyncio
import json
import sys
import os

# Add the code/python directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code', 'python'))

from core import conversation_history

async def main():
    # The conversation ID we're interested in
    conversation_id = "1755982379041"
    
    print(f"Getting conversation {conversation_id} from database...")
    
    # Get the conversation data
    conv_data = await conversation_history.get_conversation_by_id(conversation_id)
    
    if not conv_data:
        print("No conversation found")
        return
    
    print(f"Found {len(conv_data)} entries")
    
    # Write the response field to a file
    output_file = "response_field_dump.json"
    
    for i, entry in enumerate(conv_data):
        print(f"\nEntry {i+1}:")
        print(f"  conversation_id: {entry.get('conversation_id')}")
        print(f"  user_prompt: {entry.get('user_prompt')}")
        print(f"  response field type: {type(entry.get('response'))}")
        
        response_str = entry.get('response', '')
        if response_str:
            # Parse the JSON string
            try:
                response_obj = json.loads(response_str)
                
                # Write to file with pretty formatting
                with open(f"response_field_{i}.json", 'w') as f:
                    json.dump(response_obj, f, indent=2)
                
                print(f"  Written to response_field_{i}.json")
                
                # Print summary of what's in the response
                if isinstance(response_obj, dict):
                    print(f"  Response keys: {list(response_obj.keys())}")
                    if 'content' in response_obj:
                        print(f"  Content items: {len(response_obj['content'])} items")
                    if 'query_rewrite' in response_obj:
                        print(f"  Query rewrite: {response_obj['query_rewrite'].get('original_query')}")
                    if 'message_type' in response_obj:
                        print(f"  Message type: {response_obj['message_type']}")
                        
            except json.JSONDecodeError as e:
                print(f"  Failed to parse JSON: {e}")
                # Write raw string to file
                with open(f"response_field_{i}_raw.txt", 'w') as f:
                    f.write(response_str)
                print(f"  Written raw string to response_field_{i}_raw.txt")

if __name__ == "__main__":
    asyncio.run(main())