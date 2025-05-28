# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Qwen embedding implementation.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import os
import asyncio
import threading
from typing import List, Optional

from openai import AsyncOpenAI
from config.config import CONFIG

from utils.logging_config_helper import get_configured_logger, LogLevel
logger = get_configured_logger("qwen_embedding")

# Add lock for thread-safe client access
_client_lock = threading.Lock()
qwen_client = None

def get_qwen_api_key() -> str:
    """
    Retrieve the qwen API key from configuration.
    """
    # Get the API key from the embedding provider config
    provider_config = CONFIG.get_embedding_provider("qwen")
    if provider_config and provider_config.api_key:
        api_key = provider_config.api_key
        if api_key:
            return api_key
    
    # Fallback to environment variable
    api_key = os.getenv("QWEN_API_KEY")
    if not api_key:
        error_msg = "QWEN API key not found in configuration or environment"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    return api_key

def get_qwen_base_url() -> str:
    """
    Retrieve the Qwen base URL from configuration.
    """
    # Get the base URL from the embedding provider config
    provider_config = CONFIG.get_embedding_provider("qwen")
    if provider_config and provider_config.endpoint:
        base_url = provider_config.endpoint
        if base_url:
            return base_url
    
    # Fallback to environment variable
    base_url = os.getenv("QWEN_ENDPOINT")
    if not base_url:
        error_msg = "QWEN base URL not found in configuration or environment"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    return base_url


def get_async_client() -> AsyncOpenAI:
    """
    Configure and return an asynchronous Qwen client.
    """
    global qwen_client
    with _client_lock:  # Thread-safe client initialization
        if qwen_client is None:
            try:
                api_key = get_qwen_api_key()
                base_url = get_qwen_base_url()
                qwen_client = AsyncOpenAI(base_url=base_url, api_key=api_key)
                logger.debug("Qwen client initialized successfully")
            except Exception as e:
                logger.exception("Failed to initialize Qwen client")
                raise
    
    return qwen_client

async def get_qwen_embeddings(
    text: str,
    model: Optional[str] = None,
    timeout: float = 30.0
) -> List[float]:
    """
    Generate an embedding for a single text using Qwen API.
    
    Args:
        text: The text to embed
        model: Optional model ID to use, defaults to provider's configured model
        timeout: Maximum time to wait for the embedding response in seconds
        
    Returns:
        List of floats representing the embedding vector
    """
    # If model not provided, get it from config
    if model is None:
        provider_config = CONFIG.get_embedding_provider("qwen")
        if provider_config and provider_config.model:
            model = provider_config.model
        else:
            # Default to a common embedding model
            model = "text-embedding-v3"
    
    logger.debug(f"Generating Qwen embedding with model: {model}")
    logger.debug(f"Text length: {len(text)} chars")
    
    client = get_async_client()

    try:
        # Clean input text (replace newlines with spaces)
        text = text.replace("\n", " ")
        
        response = await client.embeddings.create(
            input=text,
            model=model,
            dimensions=1024,
            encoding_format="float"
        )
        
        embedding = response.data[0].embedding
        logger.debug(f"Qwen embedding generated, dimension: {len(embedding)}")
        return embedding
    except Exception as e:
        logger.exception("Error generating Qwen embedding")
        logger.log_with_context(
            LogLevel.ERROR,
            "Qwen embedding generation failed",
            {
                "model": model,
                "text_length": len(text),
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        )
        raise

async def get_qwen_batch_embeddings(
    texts: List[str],
    model: Optional[str] = None,
    timeout: float = 60.0
) -> List[List[float]]:
    """
    Generate embeddings for multiple texts using Qwen API.
    
    Args:
        texts: List of texts to embed
        model: Optional model ID to use, defaults to provider's configured model
        timeout: Maximum time to wait for the batch embedding response in seconds
        
    Returns:
        List of embedding vectors, each a list of floats
        
    Raises:
        ValueError: If input texts exceed application limit (100)
    """
    # If model not provided, get it from config
    if model is None:
        provider_config = CONFIG.get_embedding_provider("qwen")
        if provider_config and provider_config.model:
            model = provider_config.model
        else:
            model = "text-embedding-v3"
    
    MAX_BATCH_SIZE = 10  # Qwen API limit
    
    if len(texts) == 0:
        logger.warning("Received empty batch request")
        return []
        
    logger.debug(f"Generating Qwen batch embeddings with model: {model}")
    logger.debug(f"Total texts: {len(texts)}, will process in batches of {MAX_BATCH_SIZE}")
    
    client = get_async_client()
    embeddings = []
    processed_count = 0

    try:
        # Process in batches
        for i in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[i:i+MAX_BATCH_SIZE]
            cleaned_batch = [text.replace("\n", " ") for text in batch]
            
            response = await client.embeddings.create(
                input=cleaned_batch,
                model=model,
                dimensions=1024,
                encoding_format="float"
            )
            
            batch_embeddings = [data.embedding for data in sorted(response.data, key=lambda x: x.index)]
            embeddings.extend(batch_embeddings)
            processed_count += len(batch_embeddings)
            
            logger.debug(f"Processed batch {i//MAX_BATCH_SIZE+1}: "
                        f"{len(batch_embeddings)} embeddings generated")
            
        logger.debug(f"Completed all batches. Total embeddings: {processed_count}")
        return embeddings
        
    except Exception as e:
        logger.exception("Error generating Qwen batch embeddings")
        logger.log_with_context(
            LogLevel.ERROR,
            "Qwen batch embedding generation failed",
            {
                "model": model,
                "total_texts": len(texts),
                "processed_texts": processed_count,
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        )
        # Return partial results if we got some embeddings
        if embeddings:
            logger.warning(f"Returning {len(embeddings)} partial embeddings")
            return embeddings
        raise
