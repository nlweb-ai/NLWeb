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
import logging

# Suppress gRPC ALTS credentials warning (not running on GCP)
logging.getLogger("grpc").setLevel(logging.ERROR)

import google.generativeai as genai
from core.config import CONFIG

from misc.logger.logging_config_helper import get_configured_logger, LogLevel
logger = get_configured_logger("gemini_embedding")

# Add lock for thread-safe client initialization
_initialized = False
_client_lock = threading.Lock()

def configure_gemini():
    """Ensure Gemini API is configured"""
    global _initialized
    with _client_lock:
        if not _initialized:
            api_key = get_api_key()
            if not api_key:
                error_msg = "Gemini API key not found in configuration"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            genai.configure(api_key=api_key)
            _initialized = True
            logger.debug("GenAI configured successfully")
    return True

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
    
    # Get Gemini to ensure configured
    configure_gemini()
    
    while True:
        try:
            # Use asyncio.to_thread to make the synchronous GenAI call
            # non-blocking
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda t=text: genai.embed_content(
                        model=model,
                        content=t,
                        task_type=task_type
                    )
                ),
                timeout=timeout
            )
            
            # Extract the embedding values from the response
            embedding = result['embedding']
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
    
    # Call Gemini to ensure configured
    configure_gemini()
    embeddings = []
    
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
                        lambda t=text: genai.embed_content(
                            model=model,
                            content=t,
                            task_type=task_type
                        )
                    ),
                    timeout=timeout
                )

                # Extract the embedding values from the response
                embeddings.append(result['embedding'])
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
