# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Very simple wrapper around the various LLM providers.  

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.

"""

from typing import Optional, Dict, Any
from config.config import CONFIG
import asyncio
import threading


# Import provider instances
from llm.anthropic import provider as anthropic_provider
from llm.azure_oai import provider as azure_openai_provider
from llm.openai import provider as openai_provider
from llm.gemini import provider as gemini_provider
from llm.azure_llama import provider as llama_provider
from llm.azure_deepseek import provider as deepseek_provider
from llm.inception import provider as inception_provider
from llm.snowflake import provider as snowflake_provider

from utils.logging_config_helper import get_configured_logger, LogLevel
logger = get_configured_logger("llm_wrapper")

# LLM type to provider mapping
_llm_type_providers = {
    "openai": openai_provider,
    "anthropic": anthropic_provider,
    "gemini": gemini_provider,
    "azure_openai": azure_openai_provider,
    "llama_azure": llama_provider,
    "deepseek_azure": deepseek_provider,
    "inception": inception_provider,
    "snowflake": snowflake_provider
}

async def ask_llm(
    prompt: str,
    schema: Dict[str, Any],
    provider: Optional[str] = None,
    level: str = "low",
    timeout: int = 8,
    query_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Route an LLM request to the specified endpoint, with dispatch based on llm_type.
    
    Args:
        prompt: The text prompt to send to the LLM
        schema: JSON schema that the response should conform to
        provider: The LLM endpoint to use (if None, use preferred endpoint from config)
        level: The model tier to use ('low' or 'high')
        timeout: Request timeout in seconds
        query_params: Optional query parameters for development mode provider override
        
    Returns:
        Parsed JSON response from the LLM
        
    Raises:
        ValueError: If the endpoint is unknown or response cannot be parsed
        TimeoutError: If the request times out
    """
    # Determine provider, with development mode override support
    provider_name = provider or CONFIG.preferred_llm_endpoint
    
    # In development mode, allow query param override
    if CONFIG.is_development_mode() and query_params:
        from utils.utils import get_param
        override_provider = get_param(query_params, "llm_provider", str, None)
        if override_provider:
            provider_name = override_provider
            logger.debug(f"Development mode: LLM provider overridden to {provider_name}")
        
        # Also allow level override in development mode
        override_level = get_param(query_params, "llm_level", str, None)
        if override_level:
            level = override_level
            logger.debug(f"Development mode: LLM level overridden to {level}")
    logger.debug(f"Initiating LLM request with provider: {provider_name}, level: {level}")
    logger.debug(f"Prompt preview: {prompt[:100]}...")
    logger.debug(f"Schema: {schema}")
    
    if provider_name not in CONFIG.llm_endpoints:
        error_msg = f"Unknown provider '{provider_name}'"
        logger.error(error_msg)
        print(f"Unknown provider '{provider_name}'")
        return {}

    # Get provider config using the helper method
    provider_config = CONFIG.get_llm_provider(provider_name)
    if not provider_config or not provider_config.models:
        error_msg = f"Missing model configuration for provider '{provider_name}'"
        logger.error(error_msg)
        return {}

    # Get llm_type for dispatch
    llm_type = provider_config.llm_type
    logger.debug(f"Using LLM type: {llm_type}")

    model_id = getattr(provider_config.models, level)
    logger.debug(f"Using model: {model_id}")
    
    # Initialize variables for exception handling
    llm_type_for_error = llm_type

    try:

        # Get the provider instance based on llm_type
        if llm_type not in _llm_type_providers:
            error_msg = f"No implementation for LLM type '{llm_type}'"
            logger.error(error_msg)
            return {}
            
        provider_instance = _llm_type_providers[llm_type]
        
        # Simply call the provider's get_completion method without locking
        # Each provider should handle thread-safety internally
        logger.debug(f"Calling {llm_type} provider completion for endpoint {provider_name}")
        result = await asyncio.wait_for(
            provider_instance.get_completion(prompt, schema, model=model_id),
            timeout=timeout
        )
        logger.debug(f"{provider_name} response received, size: {len(str(result))} chars")
        return result
        
    except asyncio.TimeoutError:
        logger.error(f"LLM call timed out after {timeout}s with provider {provider_name}")
        return {}
    except Exception as e:
        error_msg = f"LLM call failed: {type(e).__name__}: {str(e)}"
        logger.error(f"Error with provider {provider_name}: {error_msg}")
        print(f"LLM Error ({provider_name}): {type(e).__name__}: {str(e)}")

        logger.log_with_context(
            LogLevel.ERROR,
            "LLM call failed",
            {
                "endpoint": provider_name,
                "llm_type": llm_type_for_error,
                "model": model_id,
                "level": level,
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        )

        return {}


def get_available_providers() -> list:
    """
    Get a list of LLM providers that have their required API keys available.
    
    Returns:
        List of provider names that are available for use.
    """
    available_providers = []
    
    for provider_name, provider_config in CONFIG.llm_endpoints.items():
        # Check if provider config exists and has required fields
        if (provider_config and 
            hasattr(provider_config, 'api_key') and provider_config.api_key and 
            provider_config.api_key.strip() != "" and
            hasattr(provider_config, 'models') and provider_config.models and
            provider_config.models.high and provider_config.models.low):
            available_providers.append(provider_name)
    
    return available_providers
