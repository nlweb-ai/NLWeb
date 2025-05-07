# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
OpenAI wrapper  

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.

"""

import os
import json
import re
import logging
import asyncio
from typing import Dict, Any, List

from openai import AsyncOpenAI
from config.config import CONFIG
import threading

logger = logging.getLogger(__name__)


class ConfigurationError(RuntimeError):
    """
    Raised when configuration is missing or invalid.
    """
    pass


def get_openai_api_key() -> str:
    """
    Retrieve the OpenAI API key from environment or raise an error.
    """
    # Get the API key from the preferred provider config
    preferred_provider = CONFIG.preferred_provider
    provider_config = CONFIG.providers[preferred_provider]

    key = None
    if provider_config and provider_config.api_key:
        api_key = provider_config.api_key
        if api_key:
            api_key = api_key.strip('"')  # Remove quotes if present
            key = api_key
    if not key:
        raise ConfigurationError(f"API key is not set")
    return key

_client_lock = threading.Lock()
openai_client = None

def get_async_client() -> AsyncOpenAI:
    """
    Configure and return an asynchronous OpenAI client.
    """
    global openai_client
    with _client_lock:  # Thread-safe client initialization
        if openai_client is None:
            api_key = get_openai_api_key()
            openai_client = AsyncOpenAI(api_key=api_key)
    return openai_client


def _build_messages(prompt: str, schema: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Construct the system and user message sequence enforcing a JSON schema.
    """
    return [
        {
            "role": "system",
            "content": (
                f"Provide a valid JSON response matching this schema: "
                f"{json.dumps(schema)}"
            )
        },
        {"role": "user", "content": prompt}
    ]


def clean_response(content: str) -> Dict[str, Any]:
    """
    Strip markdown fences and extract the first JSON object.
    """
    cleaned = re.sub(r"```(?:json)?\s*", "", content).strip()
    match = re.search(r"(\{.*\})", cleaned, re.S)
    if not match:
        logger.error("Failed to parse JSON from content: %r", content)
        raise ValueError("No JSON object found in response")
    return json.loads(match.group(1))


async def get_openai_completion(
    prompt: str,
    schema: Dict[str, Any],
    model: str = None,  # Make model optional
    temperature: float = 0.7,
    max_tokens: int = 2048,
    timeout: float = 30.0
) -> Dict[str, Any]:
    """
    Send an async chat completion request and return parsed JSON output.
    """
    # If model not provided, get it from config
    if model is None:
        preferred_provider = CONFIG.preferred_provider
        provider_config = CONFIG.providers[preferred_provider]
        # Use the 'high' model for completions by default
        model = provider_config.models.high
    
    client = get_async_client()
    messages = _build_messages(prompt, schema)

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ),
            timeout
        )
    except asyncio.TimeoutError:
        logger.error("Completion request timed out after %s seconds", timeout)
        raise

    return clean_response(response.choices[0].message.content)


async def get_openai_embeddings(
    text: str,
    model: str = None,  # Make model optional
    timeout: float = 30.0
) -> List[float]:
    """
    Send an async embedding request and return the embedding vector.
    """
    # If model not provided, get it from config
    if model is None:
        preferred_provider = CONFIG.preferred_provider
        provider_config = CONFIG.providers[preferred_provider]
        embedding_model_env_var = provider_config.embedding_model
        
        if embedding_model_env_var:
            model = os.getenv(embedding_model_env_var)
        
        # Use default if still not set
        if not model:
            model = "text-embedding-3-small"
    
    client = get_async_client()

    try:
        response = await asyncio.wait_for(
            client.embeddings.create(input=text, model=model),
            timeout
        )
    except asyncio.TimeoutError:
        logger.error("Embedding request timed out after %s seconds", timeout)
        raise

    return response.data[0].embedding
