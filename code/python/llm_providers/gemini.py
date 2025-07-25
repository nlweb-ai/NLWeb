# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Gemini wrapper for LLM functionality, using Google Developer API.
Reference: https://ai.google.dev/gemini-api/docs

WARNING: This code is under development and may undergo changes in future
releases. Backwards compatibility is not guaranteed at this time.
"""

import os
import json
import re
import logging
import asyncio
from typing import Dict, Any, Optional

from google import genai
from core.config import CONFIG
import threading

from llm_providers.llm_provider import LLMProvider
from misc.logger.logging_config_helper import get_configured_logger, LogLevel
logger = get_configured_logger("gemini")

class ConfigurationError(RuntimeError):
    """Raised when configuration is missing or invalid."""
    pass


class GeminiProvider(LLMProvider):
    """Implementation of LLMProvider for Google's Gemini API."""
    
    _client_lock = threading.Lock()
    _client = None

    @classmethod
    def get_api_key(cls) -> str:
        """Retrieve the API key for Gemini API."""
        provider_config = CONFIG.llm_endpoints["gemini"]
        if provider_config and provider_config.api_key:
            api_key = provider_config.api_key
            if api_key:
                api_key = api_key.strip('"')  # Remove quotes if present
                return api_key
        return None

    @classmethod
    def get_model_from_config(cls, high_tier=False) -> str:
        """Get the appropriate model from configuration based on tier."""
        provider_config = CONFIG.llm_endpoints.get("gemini")
        if provider_config and provider_config.models:
            model_name = provider_config.models.high if high_tier else provider_config.models.low
            if model_name:
                return model_name
        # Default values if not found
        default_model = "gemma-3n-e4b-it" if high_tier else "gemma-3n-e4b-it"
        return default_model

    @classmethod
    def get_client(cls):
        """Get or create the GenAI client."""
        with cls._client_lock:
            if cls._client is None:
                api_key = cls.get_api_key()
                if not api_key:
                    error_msg = "Gemini API key not found in configuration"
                    logger.error(error_msg)
                    raise ConfigurationError(error_msg)

                cls._client = genai.Client(api_key=api_key)
                logger.debug("Gemini client initialized successfully")
            return cls._client

    @classmethod
    def clean_response(cls, content: str) -> Dict[str, Any]:
        """
        Clean and extract JSON content from response text.
        """
        # Handle None content case
        if content is None:
            logger.warning("Received None content from Gemini API")
            return {}
            
        # Handle empty string case
        response_text = content.strip()
        if not response_text:
            logger.warning("Received empty content from Gemini API")
            return {}
            
        # Remove markdown code block indicators if present
        response_text = response_text.replace('```json', '').replace('```', '').strip()
                
        # Find the JSON object within the response
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        
        if start_idx == -1 or end_idx == 0:
            error_msg = "No valid JSON object found in response"
            logger.error(f"{error_msg}, content: {response_text}")
            return {}
            

        json_str = response_text[start_idx:end_idx]
                
        try:
            result = json.loads(json_str)

            # check if the value is a integer number, convert it to int
            for key, value in result.items():
                if isinstance(value, str) and re.match(r'^\d+$', value):
                    result[key] = int(value)
            return result
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse response as JSON: {e}"
            logger.error(f"{error_msg}, content: {json_str}")
            return {}

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
        """Async chat completion using Google GenAI."""
        # If model not provided, get it from config
        model_to_use = model if model else self.get_model_from_config(high_tier)
        
        # Get the GenAI client
        client = self.get_client()

        system_prompt = f"""Provide a response that matches this JSON schema: {json.dumps(schema)}"""
        
        logger.debug(f"Sending completion request to Gemini API with model: {model_to_use}")
        
        # Map max_tokens to max_output_tokens
        max_output_tokens = kwargs.get("max_output_tokens", max_tokens)
        
        config = {
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
            "system_instruction": system_prompt,
            # "response_mime_type": "application/json",
        }
        # logger.debug(f"\t\tRequest config: {config}")
        # logger.debug(f"\t\tPrompt content: {prompt}...")  # Log first 100 chars
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: client.models.generate_content(
                        model=model_to_use,
                        contents=prompt,
                        config=config
                    )
                ),
                timeout=timeout
            )
            if not response or not hasattr(response, 'text') or \
               not response.text:
                logger.error("Invalid or empty response from Gemini")
                return {}
            logger.debug("Received response from Gemini API")
            logger.debug(f"\t\tResponse content: {response.text}...")  # Log first 100 chars
            # Extract the response text
            content = response.text
            return self.clean_response(content)
        except asyncio.TimeoutError:
            logger.error(
                "Gemini completion request timed out after %s seconds", timeout
            )
            return {}
        except Exception as e:
            logger.error(
                f"Gemini completion failed: {type(e).__name__}: {str(e)}"
            )
            raise


# Create a singleton instance
provider = GeminiProvider()

# For backwards compatibility
get_gemini_completion = provider.get_completion
