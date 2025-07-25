# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Azure OpenAI embedding implementation.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import json
import asyncio
import threading
from typing import List, Optional
from openai import AsyncAzureOpenAI
from core.config import CONFIG

from misc.logger.logging_config_helper import get_configured_logger, LogLevel
logger = get_configured_logger("azure_oai_embedding")

# Global client with thread-safe initialization
_client_lock = threading.Lock()
azure_openai_client = None

def get_azure_openai_endpoint():
    """Get the Azure OpenAI endpoint from configuration."""
    provider_config = CONFIG.get_embedding_provider("azure_openai")
    if provider_config and provider_config.endpoint:
        endpoint = provider_config.endpoint
        if endpoint:
            endpoint = endpoint.strip('"')  # Remove quotes if present
            return endpoint
    return None

def get_azure_openai_api_key():
    """Get the Azure OpenAI API key from configuration."""
    provider_config = CONFIG.get_embedding_provider("azure_openai")
    if provider_config and provider_config.api_key:
        api_key = provider_config.api_key
        if api_key:
            api_key = api_key.strip('"')  # Remove quotes if present
            return api_key
    return None

def get_azure_openai_api_version():
    """Get the Azure OpenAI API version from configuration."""
    provider_config = CONFIG.get_embedding_provider("azure_openai")
    if provider_config and provider_config.api_version:
        api_version = provider_config.api_version
        return api_version
    # Default value if not found in config
    default_version = "2024-10-21"
    return default_version

def get_azure_openai_client():
    """Get or initialize the Azure OpenAI client."""
    global azure_openai_client
    with _client_lock:  # Thread-safe client initialization
        if azure_openai_client is None:
            endpoint = get_azure_openai_endpoint()
            api_key = get_azure_openai_api_key()
            api_version = get_azure_openai_api_version()
            
            if not all([endpoint, api_key, api_version]):
                error_msg = "Missing required Azure OpenAI configuration"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            try:
                azure_openai_client = AsyncAzureOpenAI(
                    azure_endpoint=endpoint,
                    api_key=api_key,
                    api_version=api_version,
                    timeout=30.0  # Set timeout explicitly
                )
                logger.debug("Azure OpenAI client initialized successfully")
            except Exception as e:
                logger.exception("Failed to initialize Azure OpenAI client")
                raise
           
    return azure_openai_client

async def get_azure_embedding(
    text: str, 
    model: Optional[str] = None,
    timeout: float = 30.0
) -> List[float]:
    """
    Generate embeddings using Azure OpenAI.
    
    Args:
        text: The text to embed
        model: The model deployment name to use (optional)
        timeout: Maximum time to wait for the embedding response in seconds
        
    Returns:
        List of floats representing the embedding vector
    """
    client = get_azure_openai_client()
    
    # If model is not provided, get from config
    if model is None:
        provider_config = CONFIG.get_embedding_provider("azure_openai")
        if provider_config and provider_config.model:
            model = provider_config.model
        else:
            # Default to a common embedding model name
            model = "text-embedding-3-small"
    
    logger.debug(f"Generating Azure OpenAI embedding with model: {model}")
    logger.debug(f"Text length: {len(text)} chars")
    
    try:
        response = await client.embeddings.create(
            input=text,
            model=model
        )
        
        embedding = response.data[0].embedding
        logger.debug(f"Azure OpenAI embedding generated, dimension: {len(embedding)}")
        return embedding
    except Exception as e:
        logger.exception("Error generating Azure OpenAI embedding")
        logger.log_with_context(
            LogLevel.ERROR,
            "Azure OpenAI embedding generation failed",
            {
                "model": model,
                "text_length": len(text),
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        )
        raise

async def get_azure_batch_embeddings(
    texts: List[str],
    model: Optional[str] = None,
    timeout: float = 60.0
) -> List[List[float]]:
    """
    Generate embeddings for multiple texts using Azure OpenAI.
    
    Args:
        texts: List of texts to embed
        model: The model deployment name to use (optional)
        timeout: Maximum time to wait for the batch embedding response in seconds
        
    Returns:
        List of embedding vectors, each a list of floats
    """
    client = get_azure_openai_client()
    
    # If model is not provided, get from config
    if model is None:
        provider_config = CONFIG.get_embedding_provider("azure_openai")
        if provider_config and provider_config.model:
            model = provider_config.model
        else:
            # Default to a common embedding model name
            model = "text-embedding-3-small"
    
    logger.debug(f"Generating Azure OpenAI batch embeddings with model: {model}")
    logger.debug(f"Batch size: {len(texts)} texts")
    
    try:
        response = await client.embeddings.create(
            input=texts,
            model=model
        )
        
        # Extract embeddings in the same order as input texts
        embeddings = [data.embedding for data in response.data]
        logger.debug(f"Azure OpenAI batch embeddings generated, count: {len(embeddings)}")
        return embeddings
    except Exception as e:
        logger.exception("Error generating Azure OpenAI batch embeddings")
        logger.log_with_context(
            LogLevel.ERROR,
            "Azure OpenAI batch embedding generation failed",
            {
                "model": model,
                "batch_size": len(texts),
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        )
        raise