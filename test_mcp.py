#!/usr/bin/env python3
"""
Test script for MCP endpoint with JSON-RPC format
"""

import json
import requests

# Test server URL
url = "http://localhost:8000/mcp"

# Test 1: Initialize
print("Test 1: Initialize")
init_request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05"
    }
}

try:
    response = requests.post(url, json=init_request)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "-"*50 + "\n")

# Test 2: List tools
print("Test 2: List tools")
list_tools_request = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
}

try:
    response = requests.post(url, json=list_tools_request)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "-"*50 + "\n")

# Test 3: Call the ask tool
print("Test 3: Call ask tool")
ask_request = {
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
        "name": "ask",
        "arguments": {
            "query": "test query"
        }
    }
}

try:
    response = requests.post(url, json=ask_request)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "-"*50 + "\n")

# Test 4: Call the get_sites tool
print("Test 4: Call get_sites tool")
get_sites_request = {
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
        "name": "get_sites",
        "arguments": {}
    }
}

try:
    response = requests.post(url, json=get_sites_request)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")