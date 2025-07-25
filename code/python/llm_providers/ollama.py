# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.

"""

import json
from ollama import AsyncClient
import os
from core.config import CONFIG
import asyncio
import threading
import re
from typing import Dict, Any, Optional

from llm_providers.llm_provider import LLMProvider
from misc.logger.logging_config_helper import get_configured_logger, LogLevel


logger = get_configured_logger("ollama")

class OllamaProvider(LLMProvider):
    """Implementation of LLMProvider for Ollama."""

    # Global client with thread-safe initialization
    _client_lock = threading.Lock()
    _client = None

    @classmethod
    def get_ollama_endpoint(cls) -> str:
        """Get Ollama endpoint from config"""
        logger.debug("Retrieving Ollama endpoint from config")
        provider_config = CONFIG.llm_endpoints.get("ollama")
        if provider_config and provider_config.endpoint:
            endpoint = provider_config.endpoint
            if endpoint:
                endpoint = endpoint.strip('"')
                logger.debug(f"Ollama endpoint found: {endpoint[:20]}...")
                return endpoint
        error_msg = "Ollama endpoint not found in config"
        logger.warning(error_msg)
        raise ValueError(error_msg)

    @classmethod
    def get_client(cls) -> AsyncClient:
        """Get or create Ollama client"""
        with cls._client_lock:
            if cls._client is None:
                logger.info("Initializing Ollama client")
                endpoint = cls.get_ollama_endpoint()

                if not all([endpoint]):
                    error_msg = "Missing required Ollama configuration"
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                try:
                    cls._client = AsyncClient(host=endpoint)
                    logger.info("Ollama client initialized successfully")
                except Exception as e:
                    logger.error("Failed to initialize Ollama client")
                    raise RuntimeError("Failed to initialize Ollama client") from e

        return cls._client

    @classmethod
    def clean_response(cls, content: str) -> Dict[str, Any]:
        """Clean and parse Ollama response"""
        logger.debug("Cleaning Ollama response")
        response_text = content.strip()
        response_text = response_text.replace("```json", "").replace("```", "").strip()

        start_idx = response_text.find("{")
        end_idx = response_text.rfind("}") + 1
        if start_idx == -1 or end_idx == 0:
            error_msg = "No valid JSON object found in response"
            logger.error(error_msg)
            return {}

        json_str = response_text[start_idx:end_idx]

        try:
            result = json.loads(json_str)
            logger.debug("Successfully parsed JSON response")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse response as JSON: {e}")
            return {}

    async def get_completion(
        self,
        prompt: str,
        schema: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: float = 60.0,
        **kwargs,
    ) -> Dict[str, Any]:
        """Get completion from Ollama"""
        if model is None:
            # Get model from config if not provided
            provider_config = CONFIG.llm_endpoints.get("ollama")
            model = provider_config.models.high if provider_config else "llama3"

        logger.info(f"Getting Ollama completion with model: {model}")
        logger.debug(f"Temperature: {temperature}, Timeout: {timeout}s")

        client = self.get_client()
        system_prompt = f"""You are a helpful assistant that provides responses in JSON format.
Your response must be valid JSON that matches this schema: {json.dumps(schema)}
Only output the JSON object, no additional text or explanation."""

        try:
            response = await asyncio.wait_for(
                client.chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    model=model,
                    options={
                        "temperature": temperature,
                    },
                    format="json",  # Force JSON response
                ),
                timeout=timeout,
            )
            content = response.message.content

            logger.debug(f"Raw response length: {len(content)} chars")

            result = self.clean_response(content)
            logger.info("Ollama completion successful")
            return result

        except asyncio.TimeoutError:
            logger.error(f"Ollama completion timed out after {timeout}s")
            return {}
        except Exception as e:
            logger.error(f"Ollama completion failed: {type(e).__name__}: {str(e)}")
            raise


# Create a singleton instance
provider = OllamaProvider()

# For backwards compatibility
get_ollama_completion = provider.get_completion
