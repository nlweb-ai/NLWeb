# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.

Code for calling Azure Open AI endpoints for LLM functionality.
"""

import json
from openai import AsyncAzureOpenAI
from config.config import CONFIG
import asyncio
import threading
from typing import Dict, Any, Optional

from llm.llm_provider import LLMProvider
from utils.logging_config_helper import get_configured_logger, LogLevel
logger = get_configured_logger("azure_oai")


class AzureOpenAIProvider(LLMProvider):
    """Implementation of LLMProvider for Azure OpenAI."""
    
    # Global client with thread-safe initialization
    _client_lock = threading.Lock()
    _client = None


    @classmethod
    def get_azure_endpoint(cls) -> str:
        """Get the Azure OpenAI endpoint from configuration."""
        provider_config = CONFIG.llm_providers.get("azure_openai")
        if provider_config and provider_config.endpoint:
            endpoint = provider_config.endpoint
            if endpoint:
                endpoint = endpoint.strip('"')  # Remove quotes if present
                return endpoint
        return None

    @classmethod
    def get_api_key(cls) -> str:
        """Get the Azure OpenAI API key from configuration."""
        provider_config = CONFIG.llm_providers.get("azure_openai")
        if provider_config and provider_config.api_key:
            api_key = provider_config.api_key
            if api_key:
                api_key = api_key.strip('"')  # Remove quotes if present
                return api_key
        return None

    @classmethod
    def get_api_version(cls) -> str:
        """Get the Azure OpenAI API version from configuration."""
        provider_config = CONFIG.llm_providers.get("azure_openai")
        if provider_config and provider_config.api_version:
            api_version = provider_config.api_version
            return api_version
        # Default value if not found in config
        default_version = "2024-02-01"
        return default_version

    @classmethod
    def get_model_from_config(cls, high_tier=False) -> str:
        """Get the appropriate model from configuration based on tier."""
        provider_config = CONFIG.llm_providers.get("azure_openai")
        if provider_config and provider_config.models:
            model_name = provider_config.models.high if high_tier else provider_config.models.low
            if model_name:
                return model_name
        # Default values if not found
        default_model = "gpt-4.1" if high_tier else "gpt-4.1-mini"
        return default_model

    @classmethod
    def get_client(cls) -> AsyncAzureOpenAI:
        """Get or initialize the Azure OpenAI client."""
        with cls._client_lock:  # Thread-safe client initialization
            if cls._client is None:
                endpoint = cls.get_azure_endpoint()
                api_key = cls.get_api_key()
                api_version = cls.get_api_version()
                if not all([endpoint, api_key, api_version]):
                    error_msg = "Missing required Azure OpenAI configuration"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                    
                try:
                    cls._client = AsyncAzureOpenAI(
                        azure_endpoint=endpoint,
                        api_key=api_key,
                        api_version=api_version,
                        timeout=30.0  # Set timeout explicitly
                    )
                    logger.debug("Azure OpenAI client initialized successfully")
                except Exception as e:
                    logger.exception("Failed to initialize Azure OpenAI client")
                    raise
               
        return cls._client

    @classmethod
    def clean_response(cls, content: str) -> Dict[str, Any]:
        """
        Clean and extract JSON content from OpenAI response.
        
        Args:
            content: The content to clean. May be None.
            
        Returns:
            Parsed JSON object or empty dict if content is None or invalid
            
        Raises:
            ValueError: If the content doesn't contain a valid JSON object
        """
        # Handle None content case
        if content is None:
            logger.warning("Received None content from Azure OpenAI")
            return {}
            
        # Handle empty string case
        response_text = content.strip()
        if not response_text:
            logger.warning("Received empty content from Azure OpenAI")
            return {}
            
        # Remove markdown code block indicators if present
        response_text = response_text.replace('```json', '').replace('```', '').strip()
                
        # Find the JSON object within the response
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        
        if start_idx == -1 or end_idx == 0:
            error_msg = "No valid JSON object found in response"
            logger.error(f"{error_msg}, content: {response_text}")
            raise ValueError(error_msg)
            

        json_str = response_text[start_idx:end_idx]
                
        try:
            result = json.loads(json_str)
            return result
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse response as JSON: {e}"
            logger.error(f"{error_msg}, content: {json_str}")
            #raise ValueError(error_msg)

    async def get_completion(
        self,
        prompt: str,
        schema: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: float = 8.0,
        high_tier: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get completion from Azure OpenAI.
        
        Args:
            prompt: The prompt to send to the model
            schema: JSON schema for the expected response
            model: Specific model to use (overrides configuration)
            temperature: Model temperature
            max_tokens: Maximum tokens in the generated response
            timeout: Request timeout in seconds
            high_tier: Whether to use the high-tier model from config
            **kwargs: Additional provider-specific arguments
            
        Returns:
            Parsed JSON response
            
        Raises:
            ValueError: If the response cannot be parsed as valid JSON
            TimeoutError: If the request times out
        """
        # Use specified model or get from config based on tier
        model_to_use = model if model else self.get_model_from_config(high_tier)
        
        client = self.get_client()
        system_prompt = f"""Provide a response that matches this JSON schema: {json.dumps(schema)}"""
        
        logger.debug(f"Sending completion request to Azure OpenAI with model: {model_to_use}")
        
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=0.1,
                    stream=False,
                    presence_penalty=0.0,
                    frequency_penalty=0.0,
                    model=model_to_use
                ),
                timeout=timeout
            )
            
            # Safely extract content from response, handling potential None
            if not response or not hasattr(response, 'choices') or not response.choices:
                logger.error("Invalid or empty response from Azure OpenAI")
                raise ValueError("Invalid or empty response structure from Azure OpenAI")
                
            # Check if message and content exist
            if not hasattr(response.choices[0], 'message') or not hasattr(response.choices[0].message, 'content'):
                logger.error("Response does not contain expected 'message.content' structure")
                return {}
                
            ansr_str = response.choices[0].message.content
            ansr = self.clean_response(ansr_str)
            return ansr
            
        except asyncio.TimeoutError:
            logger.error(f"Azure OpenAI request timed out after {timeout} seconds")
            raise
        except Exception as e:
            logger.exception(f"Error in Azure OpenAI completion: {str(e)}")
            raise


# Create a singleton instance
provider = AzureOpenAIProvider()

# For backwards compatibility
get_azure_openai_completion = provider.get_completion
