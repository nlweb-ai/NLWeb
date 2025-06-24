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
import subprocess
import sys


from utils.logging_config_helper import get_configured_logger, LogLevel
logger = get_configured_logger("llm_wrapper")

# Cache for loaded providers
_loaded_providers = {}

# Mapping of LLM types to their required pip packages
_llm_type_packages = {
    "openai": ["openai>=1.12.0"],
    "anthropic": ["anthropic>=0.18.1"],
    "gemini": ["google-cloud-aiplatform>=1.38.0"],
    "azure_openai": ["openai>=1.12.0"],
    "llama_azure": ["openai>=1.12.0"],
    "deepseek_azure": ["openai>=1.12.0"],
    "inception": ["aiohttp>=3.9.1"],
    "snowflake": ["httpx>=0.28.1"],
    "huggingface": ["huggingface_hub>=0.31.0"],
}

# Cache for installed packages
_installed_packages = set()

def _ensure_package_installed(llm_type: str):
    """
    Ensure the required packages for an LLM type are installed.
    
    Args:
        llm_type: The type of LLM provider
    """
    if llm_type not in _llm_type_packages:
        return
    
    packages = _llm_type_packages[llm_type]
    for package in packages:
        # Extract package name without version for caching
        package_name = package.split(">=")[0].split("==")[0]
        
        if package_name in _installed_packages:
            continue
            
        try:
            # Try to import the package first
            if package_name == "google-cloud-aiplatform":
                __import__("vertexai")
            elif package_name == "huggingface_hub":
                __import__("huggingface_hub")
            else:
                __import__(package_name)
            _installed_packages.add(package_name)
            logger.debug(f"Package {package_name} is already installed")
        except ImportError:
            # Package not installed, install it
            logger.info(f"Installing {package} for {llm_type} provider...")
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", package, "--quiet"
                ])
                _installed_packages.add(package_name)
                logger.info(f"Successfully installed {package}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install {package}: {e}")
                raise ValueError(f"Failed to install required package {package} for {llm_type}")

def _get_provider(llm_type: str):
    """
    Lazily load and return the provider for the given LLM type.
    
    Args:
        llm_type: The type of LLM provider to load
        
    Returns:
        The provider instance
        
    Raises:
        ValueError: If the LLM type is unknown
    """
    # Return cached provider if already loaded
    if llm_type in _loaded_providers:
        return _loaded_providers[llm_type]
    
    # Ensure required packages are installed
    _ensure_package_installed(llm_type)
    
    # Import the appropriate provider module
    try:
        if llm_type == "openai":
            from llm.openai import provider as openai_provider
            _loaded_providers[llm_type] = openai_provider
        elif llm_type == "anthropic":
            from llm.anthropic import provider as anthropic_provider
            _loaded_providers[llm_type] = anthropic_provider
        elif llm_type == "gemini":
            from llm.gemini import provider as gemini_provider
            _loaded_providers[llm_type] = gemini_provider
        elif llm_type == "azure_openai":
            from llm.azure_oai import provider as azure_openai_provider
            _loaded_providers[llm_type] = azure_openai_provider
        elif llm_type == "llama_azure":
            from llm.azure_llama import provider as llama_provider
            _loaded_providers[llm_type] = llama_provider
        elif llm_type == "deepseek_azure":
            from llm.azure_deepseek import provider as deepseek_provider
            _loaded_providers[llm_type] = deepseek_provider
        elif llm_type == "inception":
            from llm.inception import provider as inception_provider
            _loaded_providers[llm_type] = inception_provider
        elif llm_type == "snowflake":
            from llm.snowflake import provider as snowflake_provider
            _loaded_providers[llm_type] = snowflake_provider
        elif llm_type == "huggingface":
            from llm.huggingface import provider as huggingface_provider
            _loaded_providers[llm_type] = huggingface_provider
        else:
            raise ValueError(f"Unknown LLM type: {llm_type}")
            
        return _loaded_providers[llm_type]
    except ImportError as e:
        logger.error(f"Failed to import provider for {llm_type}: {e}")
        raise ValueError(f"Failed to load provider for {llm_type}: {e}")

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
        try:
            provider_instance = _get_provider(llm_type)
        except ValueError as e:
            error_msg = str(e)
            logger.error(error_msg)
            return {}
        
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
