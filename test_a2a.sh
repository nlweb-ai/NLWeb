#!/bin/bash

# Simple A2A testing script using curl

echo "========================================"
echo "Testing A2A Protocol Implementation"
echo "========================================"

BASE_URL="http://localhost:8000"

echo -e "\n1. Testing A2A info endpoint (GET /a2a)..."
curl -s "$BASE_URL/a2a" | python3 -m json.tool

echo -e "\n2. Testing A2A health endpoint..."
curl -s "$BASE_URL/a2a/health" | python3 -m json.tool

echo -e "\n3. Testing agent registration..."
curl -s -X POST "$BASE_URL/a2a" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "test-agent-1",
    "to": "nlweb",
    "type": "register",
    "content": {
      "capabilities": ["search", "analyze"]
    }
  }' | python3 -m json.tool

echo -e "\n4. Testing simple query..."
echo "Sending query: 'pasta recipes'"
curl -s -X POST "$BASE_URL/a2a" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "test-agent-1",
    "to": "nlweb",
    "type": "query",
    "content": {
      "query": "pasta recipes",
      "site": ["all"],
      "generate_mode": "list"
    }
  }' | python3 -m json.tool | head -50

echo -e "\n5. Testing agent discovery..."
curl -s -X POST "$BASE_URL/a2a" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "test-agent-2",
    "to": "nlweb",
    "type": "discover",
    "content": {}
  }' | python3 -m json.tool

echo -e "\n========================================"
echo "A2A Testing Complete!"
echo "========================================"