#!/usr/bin/env python3
"""
Check current configuration to debug test issues
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.config import CONFIG

print("🔍 Checking NLWeb Configuration")
print("="*50)

print("\n📝 Write Endpoint:")
print(f"   {CONFIG.write_endpoint}")

print("\n🗄️ Enabled Retrieval Endpoints:")
for name, config in CONFIG.retrieval_endpoints.items():
    if config.enabled:
        print(f"   {name}:")
        print(f"      - db_type: {config.db_type}")
        print(f"      - api_endpoint: {config.api_endpoint}")
        print(f"      - has_api_key: {'Yes' if config.api_key else 'No'}")

print("\n🔐 Embedding Configuration:")
print(f"   Preferred Provider: {CONFIG.preferred_embedding_provider}")
for name, config in CONFIG.embedding_providers.items():
    print(f"   {name}:")
    print(f"      - model: {config.model}")
    print(f"      - has_api_key: {'Yes' if config.api_key else 'No'}")
    print(f"      - endpoint: {config.endpoint}")

print("\n📋 Environment Variables Check:")
env_vars = [
    "AZURE_VECTOR_SEARCH_API_KEY",
    "AZURE_VECTOR_SEARCH_ENDPOINT",
    "NLWEB_WEST_API_KEY",
    "NLWEB_WEST_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT"
]

for var in env_vars:
    value = os.getenv(var)
    status = "✅ Set" if value else "❌ Not Set"
    print(f"   {var}: {status}")
