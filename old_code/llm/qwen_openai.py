# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Qwen OpenAI wrapper for LLM functionality.
"""

import threading
from typing import Dict, Any, List, Optional
import json
import re
import asyncio
from openai import AsyncOpenAI
from config.config import CONFIG
from llm.llm_provider import LLMProvider
from utils.logging_config_helper import get_configured_logger, LogLevel

logger = get_configured_logger("qwen_llm")

class QwenOpenAIProvider(LLMProvider):
    """Implementation of LLMProvider for Qwen OpenAI API."""

    _client_lock = threading.Lock()
    _client = None

    @classmethod
    def get_api_key(cls) -> str:
        """Retrieve the Qwen OpenAI API key from config."""
        provider_config = CONFIG.llm_endpoints.get("qwen_openai")
        if provider_config and provider_config.api_key:
            return provider_config.api_key.strip('"')
        raise ValueError("Qwen OpenAI API key not found in config")

    @classmethod
    def get_base_url(cls) -> str:
        """Retrieve the Qwen OpenAI endpoint from config."""
        provider_config = CONFIG.llm_endpoints.get("qwen_openai")
        if provider_config and provider_config.endpoint:
            return provider_config.endpoint.strip('"')
        raise ValueError("Qwen OpenAI endpoint not found in config")

    @classmethod
    def get_model_from_config(cls, high_tier=False) -> str:
        """Get the appropriate model from configuration based on tier."""
        provider_config = CONFIG.llm_endpoints.get("qwen_openai")
        if provider_config and provider_config.models:
            return provider_config.models.high if high_tier else provider_config.models.low
        # 默认模型
        return "qwen-plus-latest"

    @classmethod
    def get_client(cls) -> AsyncOpenAI:
        """Configure and return a thread-safe Qwen OpenAI client."""
        with cls._client_lock:
            if cls._client is None:
                api_key = cls.get_api_key()
                base_url = cls.get_base_url()
                cls._client = AsyncOpenAI(
                    api_key=api_key,
                    base_url=base_url,
                    timeout=30.0
                )
                logger.debug("Qwen OpenAI client initialized successfully")
        return cls._client

    @classmethod
    def chat(
        cls,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs
    ) -> str:
        """
        调用 Qwen OpenAI 的 chat/completions 接口。
        """
        client = cls.get_client()
        if model is None:
            model = cls.get_model_from_config()
        logger.info(f"Calling Qwen OpenAI chat model: {model}")

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            content = response.choices[0].message.content
            logger.debug(f"Qwen OpenAI chat response: {content[:100]}...")
            return content
        except Exception as e:
            logger.exception("Qwen OpenAI chat completion failed")
            raise

    @classmethod
    def completion(
        cls,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs
    ) -> str:
        """
        调用 Qwen OpenAI 的 completions 接口（如支持）。
        """
        client = cls.get_client()
        if model is None:
            model = cls.get_model_from_config()
        logger.info(f"Calling Qwen OpenAI completion model: {model}")

        try:
            response = client.completions.create(
                model=model,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            content = response.choices[0].text
            logger.debug(f"Qwen OpenAI completion response: {content[:100]}...")
            return content
        except Exception as e:
            logger.exception("Qwen OpenAI completion failed")
            raise
    
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
            provider_config = CONFIG.llm_endpoints["qwen_openai"]
            # Use the 'high' model for completions by default
            model = provider_config.models.high
        
        client = self.get_client()
        messages = self._build_messages(prompt, schema)
        logger.debug("Andy - Messages: %r", messages)

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
            raise

        return self.clean_response(response.choices[0].message.content)

# Create a singleton instance
provider = QwenOpenAIProvider()