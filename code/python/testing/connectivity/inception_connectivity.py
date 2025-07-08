import os
import sys

# Add parent directory to sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import core module that should always be available
from core.config import CONFIG

# Lazy import for OpenAI library
def get_openai_client():
    try:
        from openai import OpenAI
        return OpenAI
    except ImportError:
        return None

async def check_inception_api():
    """Check Inception API connectivity"""
    print("\nChecking Inception API connectivity...")

    # Check if Inception is configured
    if "inception" not in CONFIG.llm_endpoints:
        print("❌ Inception provider not configured")
        return False

    inception_config = CONFIG.llm_endpoints["inception"]
    api_key = inception_config.api_key

    if not api_key:
        print("❌ API key for Inception not configured")
        return False

    # Get OpenAI dependency
    OpenAI = get_openai_client()
    if not OpenAI:
        print("❌ OpenAI library not installed. Please install: pip install openai")
        return False
        
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.inceptionlabs.ai/v1")
        
        # Listing available models seems to work without an API key...
        #models = client.models.list()
        #print(f"Available models: {models}")

        # ... so instead, let's test a chat completion
        response = client.chat.completions.create(
            model=inception_config.models.high,
            messages=[{"role": "user", "content": "What is a diffusion model?"}],
            max_tokens=1000
        )
        #print(response.choices[0].message.content)
        if len(response.choices[0].message.content) > 0:
            print(f"✅ Successfully connected to Inception API")
            return True
        else:
            print("❌ Got empty message response from Inception API")
            return False

    except Exception as e:
        print(f"❌ Error connecting to Inception API: {e}")
        return False
