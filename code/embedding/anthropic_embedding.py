# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Anthropic embedding implementation.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import os
import asyncio
import threading
from typing import List, Optional

from anthropic import AsyncAnthropic
from config.config import CONFIG

from utils.logging_config_helper import get_configured_logger, LogLevel
logger = get_configured_logger("anthropic_embedding")

# Add lock for thread-safe client access
_client_lock = threading.Lock()
anthropic_client = None

def get_anthropic_api_key() -> str:
    """
    Retrieve the Anthropic API key from configuration.
    """
    # Get the API key from the embedding provider config
    provider_config = CONFIG.get_embedding_provider("anthropic")
    if provider_config and provider_config.api_key:
        api_key = provider_config.api_key
        if api_key:
            return api_key
    
    # Fallback to environment variable
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        error_msg = "Anthropic API key not found in configuration or environment"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    return api_key

def get_async_client() -> AsyncAnthropic:
    """
    Configure and return an asynchronous Anthropic client.
    """
    global anthropic_client
    with _client_lock:  # Thread-safe client initialization
        if anthropic_client is None:
            try:
                api_key = get_anthropic_api_key()
                anthropic_client = AsyncAnthropic(api_key=api_key)
                logger.debug("Anthropic client initialized successfully")
            except Exception as e:
                logger.exception("Failed to initialize Anthropic client")
                raise
    
    return anthropic_client

async def get_anthropic_embeddings(
    text: str,
    model: Optional[str] = None,
    timeout: float = 30.0
) -> List[float]:
    """
    Generate an embedding for a single text using Anthropic API.
    
    Args:
        text: The text to embed
        model: Optional model ID to use, defaults to provider's configured model
        timeout: Maximum time to wait for the embedding response in seconds
        
    Returns:
        List of floats representing the embedding vector
    """
    # If model not provided, get it from config
    if model is None:
        provider_config = CONFIG.get_embedding_provider("anthropic")
        if provider_config and provider_config.model:
            model = provider_config.model
        else:
            # Default to a common Anthropic embedding model
            model = "claude-3-embedding-v1"
    
    logger.debug(f"Generating Anthropic embedding with model: {model}")
    logger.debug(f"Text length: {len(text)} chars")
    
    client = get_async_client()

    try:
        # Anthropic's embedding API usage
        response = await client.embeddings.create(
            model=model,
            input=text,
            dimensions=1536  # Optional: specify dimensions if the model supports it
        )
        
        embedding = response.embedding
        logger.debug(f"Anthropic embedding generated, dimension: {len(embedding)}")
        return embedding
    except Exception as e:
        logger.exception("Error generating Anthropic embedding")
        logger.log_with_context(
            LogLevel.ERROR,
            "Anthropic embedding generation failed",
            {
                "model": model,
                "text_length": len(text),
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        )
        raise

# Note: Anthropic might not support native batch embedding as of now,
# so the main wrapper will handle batching by making multiple single embedding calls.