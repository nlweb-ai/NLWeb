# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Hugging Face Inference Providers wrapper for LLM functionality.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import asyncio
import json
import re
import threading
from typing import Any, Dict, List, Optional

from config.config import CONFIG
from utils.logging_config_helper import get_configured_logger

from huggingface_hub import AsyncInferenceClient
from llm.llm_provider import LLMProvider


logger = get_configured_logger("llm")


class ConfigurationError(RuntimeError):
    """
    Raised when configuration is missing or invalid.
    """

    pass


class HuggingFaceProvider(LLMProvider):
    """Implementation of LLMProvider for Hugging Face Inference Providers."""

    _client_lock = threading.Lock()
    _client = None

    @classmethod
    def get_api_key(cls) -> str:
        """
        Retrieve the Hugging Face API key from environment or raise an error.
        """
        # Get the API key from the preferred provider config
        provider_config = CONFIG.llm_providers["huggingface"]
        api_key = provider_config.api_key
        return api_key

    @classmethod
    def get_client(cls) -> AsyncInferenceClient:
        """
        Configure and return an asynchronous Hugging Face client.
        """
        with cls._client_lock:  # Thread-safe client initialization
            if cls._client is None:
                api_key = cls.get_api_key()
                cls._client = AsyncInferenceClient(provider="auto", api_key=api_key)
        return cls._client

    @classmethod
    def _build_messages(cls, prompt: str, schema: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Construct the system and user message sequence enforcing a JSON schema.
        """
        return [
            {
                "role": "system",
                "content": (f"Provide a valid JSON response matching this schema: {json.dumps(schema)}"),
            },
            {"role": "user", "content": prompt},
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
            raise ValueError("No JSON object found in response")
        return json.loads(match.group(1))

    async def get_completion(
        self,
        prompt: str,
        schema: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: float = 30.0,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Send an async chat completion request and return parsed JSON output.
        """
        # If model not provided, get it from config
        if model is None:
            print("No model provided, getting it from config")
            provider_config = CONFIG.llm_providers["huggingface"]
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
                timeout,
            )
        except asyncio.TimeoutError:
            logger.error("Completion request timed out after %s seconds", timeout)
            raise

        return self.clean_response(response.choices[0].message.content)


# Create a singleton instance
provider = HuggingFaceProvider()
