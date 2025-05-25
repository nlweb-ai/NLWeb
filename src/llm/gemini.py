# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Gemini/Vertex AI wrapper for LLM functionality.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import os
import json
import re
import logging
import asyncio
from typing import Dict, Any, List, Optional

import vertexai
from vertexai.generative_models import GenerativeModel, ChatSession
from config.config import CONFIG
import threading

from llm.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class ConfigurationError(RuntimeError):
    """Raised when configuration is missing or invalid."""
    pass


class GeminiProvider(LLMProvider):
    """Implementation of LLMProvider for Google's Gemini API."""
    
    _init_lock = threading.Lock()
    _initialized = False

    @classmethod
    def get_gcp_project(cls) -> str:
        """Retrieve the GCP project ID from the environment or raise an error."""
        # Get the project ID from the preferred provider config
        provider_config = CONFIG.llm_providers["gemini"]
        
        # For Gemini, we need the GCP project ID, which might be stored in API_KEY_ENV or a specific field
        # First check if there's a specific project env var in the config
        project_env_var = provider_config.api_key_env  # This might actually be the project ID for GCP
        
        project = os.getenv("GCP_PROJECT") or os.getenv(project_env_var)
        if not project:
            raise ConfigurationError("GCP_PROJECT is not set")
        return project

    @classmethod
    def get_gcp_location(cls) -> str:
        """Retrieve the GCP location from the environment or use default 'us-central1'."""
        return os.getenv("GCP_LOCATION", "us-central1")

    @classmethod
    def get_api_key(cls) -> Optional[str]:
        """Retrieve the API key if needed for Gemini API."""
        preferred_provider = CONFIG.preferred_llm_provider
        provider_config = CONFIG.llm_providers[preferred_provider]
        api_key_env_var = provider_config.api_key_env
        
        if api_key_env_var:
            return os.getenv(api_key_env_var)
        return None

    @classmethod
    def init_vertex_ai(cls):
        """Initialize Vertex AI with project and location."""
        with cls._init_lock:  # Thread-safe initialization
            if not cls._initialized:
                vertexai.init(
                    project=cls.get_gcp_project(),
                    location=cls.get_gcp_location()
                )
                cls._initialized = True

    @classmethod
    def get_client(cls):
        """
        For Gemini, we don't maintain a persistent client but initialize Vertex AI.
        This method ensures Vertex AI is initialized.
        """
        cls.init_vertex_ai()
        return None  # No persistent client for Gemini

    @classmethod
    def _build_messages(cls, prompt: str, schema: Dict[str, Any]) -> List[str]:
        """Construct the message sequence for JSON-schema enforcement."""
        return [
            f"Provide a valid JSON response matching this schema: {json.dumps(schema)}",
            prompt
        ]

    @classmethod
    def clean_response(cls, content: str) -> Dict[str, Any]:
        """Strip markdown fences and extract the first JSON object."""
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
        **kwargs
    ) -> Dict[str, Any]:
        """Async chat completion using Vertex AI (Gemini)."""
        # If model not provided, get it from config
        if model is None:
            provider_config = CONFIG.llm_providers["gemini"]
            # Use the 'high' model for completions by default
            model = provider_config.models.high
        
        # Ensure Vertex AI is initialized
        self.init_vertex_ai()
        generative_model = GenerativeModel(model)
        
        # Combine system and user messages
        messages = self._build_messages(prompt, schema)
        
        # Map max_tokens to max_output_tokens
        max_output_tokens = kwargs.get("max_output_tokens", max_tokens)
        
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        }

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: generative_model.generate_content(
                        messages,
                        generation_config=generation_config
                    )
                ),
                timeout
            )
        except asyncio.TimeoutError:
            logger.error("Completion request timed out after %s seconds", timeout)
            raise

        # Extract the response text
        content = response.text
        return self.clean_response(content)


# Create a singleton instance
provider = GeminiProvider()

# For backwards compatibility
get_gemini_completion = provider.get_completion