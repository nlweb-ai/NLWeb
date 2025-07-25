#!/usr/bin/env python3
"""
Test script to verify OAuth configuration endpoint behavior
"""
import os
import sys
sys.path.insert(0, '/Users/rvguha/v2/NLWeb/code/python')

from core.config import Config

def test_oauth_config():
    """Test OAuth configuration with different scenarios"""
    
    # Test 1: Check current configuration
    print("Current OAuth Configuration:")
    print("-" * 50)
    
    config = Config()
    config.init()
    
    print(f"Number of configured OAuth providers: {len(config.oauth_providers)}")
    for provider, data in config.oauth_providers.items():
        print(f"  - {provider}: has client_id={bool(data.get('client_id'))}, has client_secret={bool(data.get('client_secret'))}")
    
    if not config.oauth_providers:
        print("  No OAuth providers are enabled or properly configured.")
        print("\nTo enable OAuth providers:")
        print("  1. Set enabled: true in config/config_oauth.yaml")
        print("  2. Set the required environment variables:")
        print("     - Google: GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET")
        print("     - GitHub: GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET")
        print("     - Facebook: FACEBOOK_OAUTH_CLIENT_ID, FACEBOOK_OAUTH_CLIENT_SECRET")
        print("     - Microsoft: MICROSOFT_OAUTH_CLIENT_ID, MICROSOFT_OAUTH_CLIENT_SECRET")
    
    print("\n" + "-" * 50)
    
    # Test 2: Simulate what the API endpoint would return
    print("\nWhat /api/oauth/config would return:")
    print("-" * 50)
    
    oauth_config = {}
    for provider_name, provider_config in config.oauth_providers.items():
        if provider_config.get("client_id"):
            oauth_config[provider_name] = {
                "enabled": True,
                "client_id": provider_config["client_id"],
                "auth_url": provider_config.get("auth_url"),
                "scope": provider_config.get("scope"),
                "redirect_uri": f"http://localhost:8000/oauth/callback"
            }
            if provider_name == "facebook":
                oauth_config[provider_name]["app_id"] = provider_config["client_id"]
    
    import json
    print(json.dumps(oauth_config, indent=2))
    
    if not oauth_config:
        print("{}")
        print("\nWith this configuration, the login button will be hidden in the UI.")

if __name__ == "__main__":
    test_oauth_config()