# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Wrapper around the various embedding providers.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

from typing import Optional, List
import asyncio
import threading

from config.config import CONFIG
from utils.logging_config_helper import get_configured_logger, LogLevel

logger = get_configured_logger("embedding_wrapper")

# Add locks for thread-safe provider access
_provider_locks = {
    "openai": threading.Lock(),
    "gemini": threading.Lock(),
    "azure_openai": threading.Lock(),
    "snowflake": threading.Lock()
}

async def get_embedding(
    text: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    timeout: int = 30
) -> List[float]:
    """
    Get embedding for the provided text using the specified provider and model.
    
    Args:
        text: The text to embed
        provider: Optional provider name, defaults to preferred_embedding_provider
        model: Optional model name, defaults to the provider's configured model
        timeout: Maximum time to wait for embedding response in seconds
        
    Returns:
        List of floats representing the embedding vector
    """
    provider = provider or CONFIG.preferred_embedding_provider
    logger.debug(f"Getting embedding with provider: {provider}")
    logger.debug(f"Text length: {len(text)} chars")
    
    if provider not in CONFIG.embedding_providers:
        error_msg = f"Unknown embedding provider '{provider}'"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Get provider config using the helper method
    provider_config = CONFIG.get_embedding_provider(provider)
    if not provider_config:
        error_msg = f"Missing configuration for embedding provider '{provider}'"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Use the provided model or fall back to the configured model
    model_id = model or provider_config.model
    if not model_id:
        error_msg = f"No embedding model specified for provider '{provider}'"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    logger.debug(f"Using embedding model: {model_id}")

    try:
        # Use a timeout wrapper for all embedding calls
        if provider == "openai":
            logger.debug("Getting OpenAI embeddings")
            # Import here to avoid potential circular imports
            from embedding.openai_embedding import get_openai_embeddings
            result = await asyncio.wait_for(
                get_openai_embeddings(text, model=model_id),
                timeout=timeout
            )
            logger.debug(f"OpenAI embeddings received, dimension: {len(result)}")
            return result

        if provider == "gemini":
            logger.debug("Getting Gemini embeddings")
            # Import here to avoid potential circular imports
            from embedding.gemini_embedding import get_gemini_embeddings
            result = await asyncio.wait_for(
                get_gemini_embeddings(text, model=model_id),
                timeout=timeout
            )
            logger.debug(f"Gemini embeddings received, dimension: {len(result)}")
            return result

        if provider == "azure_openai":
            logger.debug("Getting Azure OpenAI embeddings")
            # Import here to avoid potential circular imports
            from embedding.azure_oai_embedding import get_azure_embedding
            # For Azure, model_id is the deployment_id
            result = await asyncio.wait_for(
                get_azure_embedding(text, model=model_id),
                timeout=timeout
            )
            logger.debug(f"Azure embeddings received, dimension: {len(result)}")
            return result
            
        if provider == "snowflake":
            logger.debug("Getting Snowflake embeddings")
            # Import here to avoid potential circular imports
            from embedding.snowflake_embedding import cortex_embed
            result = await asyncio.wait_for(
                cortex_embed(text, model=model_id),
                timeout=timeout
            )
            logger.debug(f"Snowflake Cortex embeddings received, dimension: {len(result)}")
            return result

        error_msg = f"No embedding implementation for provider '{provider}'"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    except asyncio.TimeoutError:
        logger.error(f"Embedding request timed out after {timeout}s with provider {provider}")
        raise
    except Exception as e:
        logger.exception(f"Error during embedding generation with provider {provider}")
        logger.log_with_context(
            LogLevel.ERROR,
            "Embedding generation failed",
            {
                "provider": provider,
                "model": model_id,
                "text_length": len(text),
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        )
        raise

async def batch_get_embeddings(
    texts: List[str],
    provider: Optional[str] = None,
    model: Optional[str] = None,
    timeout: int = 60
) -> List[List[float]]:
    """
    Get embeddings for a batch of texts.
    
    Args:
        texts: List of texts to embed
        provider: Optional provider name, defaults to preferred_embedding_provider
        model: Optional model name, defaults to the provider's configured model
        timeout: Maximum time to wait for batch embedding response in seconds
        
    Returns:
        List of embedding vectors, each a list of floats
    """
    provider = provider or CONFIG.preferred_embedding_provider
    logger.debug(f"Getting batch embeddings with provider: {provider}")
    logger.debug(f"Batch size: {len(texts)} texts")
    
    # Get provider config using the helper method
    provider_config = CONFIG.get_embedding_provider(provider)
    if not provider_config:
        error_msg = f"Missing configuration for embedding provider '{provider}'"
        logger.error(error_msg)
        raise ValueError(error_msg)
        
    model_id = model or provider_config.model
    if not model_id:
        error_msg = f"No embedding model specified for provider '{provider}'"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    try:
        # Provider-specific batch implementations with timeout handling
        if provider == "openai":
            # Use OpenAI's batch embedding API
            logger.debug("Getting OpenAI batch embeddings")
            from embedding.openai_embedding import get_openai_batch_embeddings
            result = await asyncio.wait_for(
                get_openai_batch_embeddings(texts, model=model_id),
                timeout=timeout
            )
            logger.debug(f"OpenAI batch embeddings received, count: {len(result)}")
            return result
            
        if provider == "azure_openai":
            # Use Azure's batch embedding API
            logger.debug("Getting Azure OpenAI batch embeddings")
            from embedding.azure_oai_embedding import get_azure_batch_embeddings
            result = await asyncio.wait_for(
                get_azure_batch_embeddings(texts, model=model_id),
                timeout=timeout
            )
            logger.debug(f"Azure batch embeddings received, count: {len(result)}")
            return result
            
        if provider == "snowflake":
            # Use Snowflake's batch embedding API
            logger.debug("Getting Snowflake batch embeddings")
            from embedding.snowflake_embedding import get_snowflake_batch_embeddings
            result = await asyncio.wait_for(
                get_snowflake_batch_embeddings(texts, model=model_id),
                timeout=timeout
            )
            logger.debug(f"Snowflake batch embeddings received, count: {len(result)}")
            return result
            
        if provider == "gemini":
            # Gemini might not have a native batch API, so process one by one
            logger.debug("Getting Gemini batch embeddings (sequential)")
            from embedding.gemini_embedding import get_gemini_embeddings
            # Process texts one by one with individual timeouts
            results = []
            for text in texts:
                embedding = await asyncio.wait_for(
                    get_gemini_embeddings(text, model=model_id),
                    timeout=30  # Individual timeout per text
                )
                results.append(embedding)
            logger.debug(f"Gemini batch embeddings received, count: {len(results)}")
            return results
    
        # Default implementation if provider doesn't match any above
        logger.debug(f"No specific batch implementation for {provider}, processing sequentially")
        results = []
        for text in texts:
            embedding = await get_embedding(text, provider, model)
            results.append(embedding)
        
        return results
        
    except asyncio.TimeoutError:
        logger.error(f"Batch embedding request timed out after {timeout}s with provider {provider}")
        raise
    except Exception as e:
        logger.exception(f"Error during batch embedding generation with provider {provider}")
        logger.log_with_context(
            LogLevel.ERROR,
            "Batch embedding generation failed",
            {
                "provider": provider,
                "model": model_id,
                "batch_size": len(texts),
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        )
        raise