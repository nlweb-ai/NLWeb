# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
OpenAI embedding implementation.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import os
import asyncio
import threading
from typing import List, Optional

from openai import AsyncOpenAI
from core.config import CONFIG

from misc.logger.logging_config_helper import get_configured_logger, LogLevel
logger = get_configured_logger("openai_embedding")

# Add lock for thread-safe client access
_client_lock = threading.Lock()
openai_client = None

def get_openai_api_key() -> str:
    """
    Retrieve the OpenAI API key from configuration.
    """
    # Get the API key from the embedding provider config
    provider_config = CONFIG.get_embedding_provider("openai")
    if provider_config and provider_config.api_key:
        api_key = provider_config.api_key
        if api_key:
            return api_key
    
    # Fallback to environment variable
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        error_msg = "OpenAI API key not found in configuration or environment"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    return api_key

def get_async_client() -> AsyncOpenAI:
    """
    Configure and return an asynchronous OpenAI client.
    """
    global openai_client
    with _client_lock:  # Thread-safe client initialization
        if openai_client is None:
            try:
                api_key = get_openai_api_key()
                openai_client = AsyncOpenAI(api_key=api_key)
                logger.debug("OpenAI client initialized successfully")
            except Exception as e:
                logger.exception("Failed to initialize OpenAI client")
                raise
    
    return openai_client

async def get_openai_embeddings(
    text: str,
    model: Optional[str] = None,
    timeout: float = 30.0
) -> List[float]:
    """
    Generate an embedding for a single text using OpenAI API.
    
    Args:
        text: The text to embed
        model: Optional model ID to use, defaults to provider's configured model
        timeout: Maximum time to wait for the embedding response in seconds
        
    Returns:
        List of floats representing the embedding vector
    """
    # If model not provided, get it from config
    if model is None:
        provider_config = CONFIG.get_embedding_provider("openai")
        if provider_config and provider_config.model:
            model = provider_config.model
        else:
            # Default to a common embedding model
            model = "text-embedding-3-small"
    
    logger.debug(f"Generating OpenAI embedding with model: {model}")
    logger.debug(f"Text length: {len(text)} chars")
    
    client = get_async_client()

    try:
        # Clean input text (replace newlines with spaces)
        text = text.replace("\n", " ")
        
        response = await client.embeddings.create(
            input=text,
            model=model
        )
        
        embedding = response.data[0].embedding
        logger.debug(f"OpenAI embedding generated, dimension: {len(embedding)}")
        return embedding
    except Exception as e:
        logger.exception("Error generating OpenAI embedding")
        logger.log_with_context(
            LogLevel.ERROR,
            "OpenAI embedding generation failed",
            {
                "model": model,
                "text_length": len(text),
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        )
        raise

async def get_openai_batch_embeddings(
    texts: List[str],
    model: Optional[str] = None,
    timeout: float = 60.0
) -> List[List[float]]:
    """
    Generate embeddings for multiple texts using OpenAI API.
    
    Args:
        texts: List of texts to embed
        model: Optional model ID to use, defaults to provider's configured model
        timeout: Maximum time to wait for the batch embedding response in seconds
        
    Returns:
        List of embedding vectors, each a list of floats
    """
    # If model not provided, get it from config
    if model is None:
        provider_config = CONFIG.get_embedding_provider("openai")
        if provider_config and provider_config.model:
            model = provider_config.model
        else:
            # Default to a common embedding model
            model = "text-embedding-3-small"
    
    logger.debug(f"Generating OpenAI batch embeddings with model: {model}")
    logger.debug(f"Batch size: {len(texts)} texts")
    
    client = get_async_client()

    try:
        # Clean input texts (replace newlines with spaces)
        cleaned_texts = [text.replace("\n", " ") for text in texts]
        
        response = await client.embeddings.create(
            input=cleaned_texts,
            model=model
        )
        
        # Extract embeddings in the same order as input texts
        # Use sorted to ensure correct ordering by index
        embeddings = [data.embedding for data in sorted(response.data, key=lambda x: x.index)]
        logger.debug(f"OpenAI batch embeddings generated, count: {len(embeddings)}")
        return embeddings
    except Exception as e:
        logger.exception("Error generating OpenAI batch embeddings")
        logger.log_with_context(
            LogLevel.ERROR,
            "OpenAI batch embedding generation failed",
            {
                "model": model,
                "batch_size": len(texts),
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        )
        raise