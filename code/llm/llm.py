# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Very simple wrapper around the various LLM providers.  

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.

"""

from typing import Optional, Dict, Any, List
from config.config import CONFIG
import asyncio
import threading

from llm.azure_oai import get_azure_openai_completion
from llm.openai import get_openai_completion
from llm.anthropic import get_anthropic_completion
from llm.gemini import get_gemini_completion
from llm.azure_llama import get_llama_completion
from llm.azure_deepseek import get_deepseek_completion
from llm.inceptionlabs import get_inceptionlabs_completion

from utils.logging_config_helper import get_configured_logger, LogLevel
logger = get_configured_logger("llm_wrapper")

# Add locks for thread-safe provider access
_provider_locks = {
    "openai": threading.Lock(),
    "anthropic": threading.Lock(),
    "gemini": threading.Lock(),
    "azure_openai": threading.Lock()
}

async def ask_llm(
    prompt: str,
    schema: Dict[str, Any],
    provider: Optional[str] = None,
    level: str = "low",
    timeout: int = 8
) -> Dict[str, Any]:
    
    provider = provider or CONFIG.preferred_provider
    logger.debug(f"Initiating LLM request with provider: {provider}, level: {level}")
    logger.debug(f"Prompt preview: {prompt[:100]}...")
    logger.debug(f"Schema: {schema}")
    
    if provider not in CONFIG.providers:
        error_msg = f"Unknown provider '{provider}'"
        logger.error(error_msg)
        print(f"Unknown provider '{provider}'")
        raise ValueError(error_msg)

    model_id = getattr(CONFIG.providers[provider].models, level)
    logger.debug(f"Using model: {model_id}")

    try:
        # Use timeout wrapper for all LLM calls
        if provider == "openai":
            logger.debug("Calling OpenAI completion")
            result = await asyncio.wait_for(
                get_openai_completion(prompt, schema, model=model_id),
                timeout=timeout
            )
            logger.debug(f"OpenAI response received, size: {len(str(result))} chars")
            return result

        if provider == "anthropic":
            logger.debug("Calling Anthropic completion")
            result = await asyncio.wait_for(
                get_anthropic_completion(prompt, schema, model=model_id),
                timeout=timeout
            )
            logger.debug(f"Anthropic response received, size: {len(str(result))} chars")
            return result

        if provider == "gemini":
            logger.debug("Calling Gemini completion")
            result = await asyncio.wait_for(
                get_gemini_completion(prompt, schema, model=model_id),
                timeout=timeout
            )
            logger.debug(f"Gemini response received, size: {len(str(result))} chars")
            return result

        if provider == "azure_openai":
            logger.debug("Calling Azure OpenAI completion")
            result = await asyncio.wait_for(
                get_azure_openai_completion(prompt, schema, model=model_id),
                timeout=timeout
            )
            logger.debug(f"Azure OpenAI response received, size: {len(str(result))} chars")
            return result

        error_msg = f"No implementation for provider '{provider}'"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    except asyncio.TimeoutError:
        logger.error(f"LLM call timed out after {timeout}s with provider {provider}")
        raise
    except Exception as e:
        logger.exception(f"Error during LLM call with provider {provider}")
        logger.log_with_context(
            LogLevel.ERROR,
            "LLM call failed",
            {
                "provider": provider,
                "model": model_id,
                "level": level,
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        )
        raise


async def get_embedding(
    text: str,
    provider: Optional[str] = None,
    quality: str = "high"
) -> List[float]:
    provider = provider or CONFIG.preferred_provider
    logger.info(f"Getting embedding with provider: {provider}, quality: {quality}")
    logger.debug(f"Text length: {len(text)} chars")
    
    if provider not in CONFIG.providers:
        error_msg = f"Unknown provider '{provider}'"
        logger.error(error_msg)
        raise ValueError(error_msg)

    model_id = getattr(CONFIG.providers[provider].models, quality)
    logger.debug(f"Using embedding model: {model_id}")

    try:
        if provider == "openai":
            logger.debug("Getting OpenAI embeddings")
            from llm.openai import get_openai_embeddings as openai_embed
            result = await openai_embed(text)
            logger.debug(f"OpenAI embeddings received, dimension: {len(result)}")
            return result

        if provider == "gemini":
            logger.debug("Getting Gemini embeddings")
            from llm.gemini import get_gemini_embeddings as gem_embed
            result = await gem_embed(text, model=model_id)
            logger.debug(f"Gemini embeddings received, dimension: {len(result)}")
            return result

        if provider == "azure_openai":
            logger.debug("Getting Azure OpenAI embeddings")
            from llm.azure_oai import get_azure_embedding as azure_embed
            # here model_id is the deployment_id
            result = await azure_embed(text)
            logger.debug(f"Azure embeddings received, dimension: {len(result)}")
            return result

        error_msg = f"No implementation for provider '{provider}'"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    except Exception as e:
        logger.exception(f"Error during embedding generation with provider {provider}")
        logger.log_with_context(
            LogLevel.ERROR,
            "Embedding generation failed",
            {
                "provider": provider,
                "model": model_id,
                "quality": quality,
                "text_length": len(text),
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        )
        raise
