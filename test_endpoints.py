#!/usr/bin/env python3
"""Test various endpoints of the aiohttp server"""

import requests
import json
import time

def test_endpoint(name, url, headers=None):
    """Test a single endpoint"""
    try:
        print(f"\n{name}:")
        print(f"  URL: {url}")
        
        response = requests.get(url, headers=headers, timeout=5)
        print(f"  Status: {response.status_code}")
        print(f"  Headers: {dict(response.headers)}")
        
        if response.headers.get('content-type', '').startswith('application/json'):
            print(f"  Body: {json.dumps(response.json(), indent=2)}")
        elif response.headers.get('content-type', '').startswith('text/event-stream'):
            print(f"  SSE Data (first 200 chars): {response.text[:200]}...")
        else:
            print(f"  Body (first 200 chars): {response.text[:200]}...")
            
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

def main():
    """Run all tests"""
    base_url = "http://localhost:8000"
    
    print("Testing aiohttp server endpoints...")
    
    # Test health endpoint
    test_endpoint("Health Check", f"{base_url}/health")
    
    # Test ready endpoint
    test_endpoint("Readiness Check", f"{base_url}/ready")
    
    # Test root (index.html)
    test_endpoint("Root (index.html)", f"{base_url}/")
    
    # Test who endpoint
    test_endpoint("Who Endpoint", f"{base_url}/who")
    
    # Test sites endpoint
    test_endpoint("Sites Endpoint", f"{base_url}/sites")
    
    # Test sites with streaming
    test_endpoint("Sites (SSE)", f"{base_url}/sites?streaming=true", 
                  headers={"Accept": "text/event-stream"})
    
    # Test ask endpoint (non-streaming)
    test_endpoint("Ask Endpoint", f"{base_url}/ask?q=test&streaming=false")
    
    # Test ask endpoint (SSE)
    print("\n\nTesting SSE streaming (this may take a moment)...")
    test_endpoint("Ask (SSE)", f"{base_url}/ask?q=test", 
                  headers={"Accept": "text/event-stream"})

if __name__ == "__main__":
    main()