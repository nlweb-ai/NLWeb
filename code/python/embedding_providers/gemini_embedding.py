# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Gemini embedding implementation using Google GenAI.

WARNING: This code is under development and may undergo changes in future
releases. Backwards compatibility is not guaranteed at this time.
"""

import os
import asyncio
import threading
from typing import List, Optional
import time

from google import genai
from google.genai import types
from core.config import CONFIG

from misc.logger.logging_config_helper import get_configured_logger, LogLevel
logger = get_configured_logger("gemini_embedding")

# Add lock for thread-safe client initialization
_client_lock = threading.Lock()
_client = None


def get_api_key() -> str:
    """
    Retrieve the API key for Gemini API from configuration.
    """
    # Get the API key from the embedding provider config
    provider_config = CONFIG.get_embedding_provider("gemini")
    
    if provider_config and provider_config.api_key:
        api_key = provider_config.api_key
        if api_key:
            return api_key.strip('"')  # Remove quotes if present
    
    # Fallback to environment variables
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        error_msg = "Gemini API key not found in configuration or environment"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    return api_key


def get_client():
    """
    Get or create the GenAI client for embeddings.
    """
    global _client
    with _client_lock:
        if _client is None:
            api_key = get_api_key()
            if not api_key:
                error_msg = "Gemini API key not found in configuration"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            _client = genai.Client(api_key=api_key)
            logger.debug("GenAI client initialized successfully")
        return _client


async def get_gemini_embeddings(
    text: str,
    model: Optional[str] = None,
    timeout: float = 30.0,
    task_type: str = "SEMANTIC_SIMILARITY"
) -> List[float]:
    """
    Generate an embedding for a single text using Google GenAI.
    
    Args:
        text: The text to embed
        model: Optional model ID to use, defaults to provider's configured
               model
        timeout: Maximum time to wait for the embedding response in seconds
        task_type: The task type for the embedding (e.g.,
                  "SEMANTIC_SIMILARITY", "RETRIEVAL_QUERY", etc.)
        
    Returns:
        List of floats representing the embedding vector
    """
    # If model not provided, get it from config
    if model is None:
        provider_config = CONFIG.get_embedding_provider("gemini")
        if provider_config and provider_config.model:
            model = provider_config.model
        else:
            # Default to a common Gemini embedding model
            model = "gemini-embedding-exp-03-07"
    
    logger.debug(f"Generating Gemini embedding with model: {model}")
    logger.debug(f"Text length: {len(text)} chars")
    
    # Get the GenAI client
    client = get_client()
    
    while True:
        try:
            # Create embedding config
            config = types.EmbedContentConfig(task_type=task_type)
            
            # Use asyncio.to_thread to make the synchronous GenAI call
            # non-blocking
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: client.models.embed_content(
                        model=model,
                        contents=text,
                        config=config
                    )
                ),
                timeout=timeout
            )
            
            # Extract the embedding values from the response
            embedding = result.embeddings[0].values
            logger.debug(
                f"Gemini embedding generated, dimension: {len(embedding)}"
            )
            return embedding
        except Exception as e:
            error_message = str(e)
            if "429" in error_message:
                error_message = "Rate limit exceeded. Please try again later."
                time.sleep(5)  # Wait before retrying
            else:
                logger.exception("Error generating Gemini embedding")
                logger.log_with_context(
                    LogLevel.ERROR,
                    "Gemini embedding generation failed",
                    {
                        "model": model,
                        "text_length": len(text),
                        "error_type": type(e).__name__,
                        "error_message": error_message
                    }
                )
                raise


async def get_gemini_batch_embeddings(
    texts: List[str],
    model: Optional[str] = None,
    timeout: float = 60.0,
    task_type: str = "SEMANTIC_SIMILARITY"
) -> List[List[float]]:
    """
    Generate embeddings for multiple texts using Google GenAI.
    
    Note: Gemini API processes embeddings one at a time, so this function
    makes multiple sequential calls for batch processing.
    
    Args:
        texts: List of texts to embed
        model: Optional model ID to use, defaults to provider's configured
               model
        timeout: Maximum time to wait for each embedding response in seconds
        task_type: The task type for the embedding (e.g.,
                  "SEMANTIC_SIMILARITY", "RETRIEVAL_QUERY", etc.)
        
    Returns:
        List of embedding vectors, each a list of floats
    """
    # If model not provided, get it from config
    if model is None:
        provider_config = CONFIG.get_embedding_provider("gemini")
        if provider_config and provider_config.model:
            model = provider_config.model
        else:
            # Default to a common Gemini embedding model
            model = "gemini-embedding-exp-03-07"
    
    logger.debug(f"Generating Gemini batch embeddings with model: {model}")
    logger.debug(f"Batch size: {len(texts)} texts")
    
    # Get the GenAI client
    client = get_client()
    embeddings = []

    # Create embedding config
    config = types.EmbedContentConfig(task_type=task_type)
    
    # Process each text individually
    for i, text in enumerate(texts):
        logger.debug(f"Processing text {i+1}/{len(texts)}")
        
        # Use asyncio.to_thread to make the synchronous GenAI call
        # non-blocking
        while True:
            try:
                # Attempt to get the embedding
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        lambda t=text: client.models.embed_content(
                            model=model,
                            contents=t,
                            config=config
                        )
                    ),
                    timeout=timeout
                )

                # Extract the embedding values from the response
                embedding = result.embeddings[0].values
                embeddings.append(embedding)
                break
            except Exception as e:
                error_message = str(e)
                if "429" in error_message:
                    error_message = "Rate limit exceeded. Retrying..."
                    time.sleep(5)
                else:
                    logger.exception("Error generating Gemini batch embedding in batch")
                    logger.log_with_context(
                        LogLevel.ERROR,
                        "Gemini batch embedding generation failed",
                        {
                            "model": model,
                            "batch_size": len(texts),
                            "text_length": len(text),
                            "error_type": type(e).__name__,
                            "error_message": error_message
                        }
                    )
                    raise
        
    logger.debug(
        f"Gemini batch embeddings generated, count: {len(embeddings)}"
    )
    return embeddings


# Note: The GenAI client handles single embeddings efficiently.
# Batch processing can be implemented by making multiple calls if needed.
