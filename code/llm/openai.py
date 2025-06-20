# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
OpenAI wrapper for LLM functionality.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import os
import json
import re
import logging
import asyncio
from typing import Dict, Any, List, Optional

from openai import AsyncOpenAI
from config.config import CONFIG
import threading
from utils.logging_config_helper import get_configured_logger
from utils.logger import LogLevel


from llm.llm_provider import LLMProvider

from utils.logging_config_helper import get_configured_logger, LogLevel
logger = get_configured_logger("llm")


class ConfigurationError(RuntimeError):
    """
    Raised when configuration is missing or invalid.
    """
    pass



class OpenAIProvider(LLMProvider):
    """Implementation of LLMProvider for OpenAI API."""
    
    _client_lock = threading.Lock()
    _client = None

    @classmethod
    def get_api_key(cls) -> str:
        """
        Retrieve the OpenAI API key from environment or raise an error.
        """
        # Get the API key from the preferred provider config
        provider_config = CONFIG.llm_endpoints["openai"]
        api_key = provider_config.api_key
        return api_key

    @classmethod
    def get_api_endpoint(cls) -> str:
        """
        Retrieve the OpenAI API endpoint from environment.

        Note: useful when you use openai client to connect to compatible llm api
        """
        # Get the API key from the preferred provider config
        provider_config = CONFIG.llm_endpoints["openai"]
        endpoint = provider_config.endpoint
    
        # Fallback to environment variable if provider_config.endpoint is not set
        if not endpoint:
            endpoint = os.getenv("OPENAI_ENDPOINT")
            if not endpoint:
                error_msg = "OpenAI API endpoint not found in configuration or environment"
                logger.error(error_msg)
                raise ValueError(error_msg)
        return endpoint


    @classmethod
    def get_client(cls) -> AsyncOpenAI:
        """
        Configure and return an asynchronous OpenAI client.
        """
        with cls._client_lock:  # Thread-safe client initialization
            if cls._client is None:
                api_key = cls.get_api_key()
                endpoint = cls.get_api_endpoint()
                if not all([endpoint, api_key]):
                    error_msg = "Missing required OpenAI configuration"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                    
                try:
                    cls._client = AsyncOpenAI(
                        api_key=api_key, base_url=endpoint,
                        timeout=30.0  # Set timeout explicitly
                    )
                    logger.debug("OpenAI client initialized successfully.\n\tEndpoint: %s", endpoint)
                except Exception as e:
                    error_msg = f"Failed to initialize OpenAI client: {e}"
                    logger.error(error_msg)
                    return None
        return cls._client

    @classmethod
    def _build_messages(cls, prompt: str, schema: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Construct the system and user message sequence enforcing a JSON schema.
        """
        return [
            {
                "role": "system",
                "content": (
                    f"Provide a valid JSON response matching this schema: "
                    f"{json.dumps(schema)}"
                )
            },
            {"role": "user", "content": prompt}
        ]

    @classmethod
    def clean_response(cls, content: str) -> Dict[str, Any]:
        """
        Strip markdown fences and extract the first JSON object.
        """
        cleaned = re.sub(r"```(?:json)?\s*", "", content).strip()
        match = re.search(r"(\{.*\})", cleaned, re.S)
        if not match:
            logger.error("Failed to parse JSON from content: %r", content)
            return {}
        return json.loads(match.group(1))

    async def get_completion(
        self,
        prompt: str,
        schema: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: float = 30.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send an async chat completion request and return parsed JSON output.
        """
        # If model not provided, get it from config
        if model is None:
            provider_config = CONFIG.llm_endpoints["openai"]
            # Use the 'high' model for completions by default
            model = provider_config.models.high
        
        client = self.get_client()
        messages = self._build_messages(prompt, schema)

        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                timeout
            )
        except asyncio.TimeoutError:
            logger.error("Completion request timed out after %s seconds", timeout)
            return {}

        try:
            return self.clean_response(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Error processing OpenAI response: {e}")
            return {}



# Create a singleton instance
provider = OpenAIProvider()
