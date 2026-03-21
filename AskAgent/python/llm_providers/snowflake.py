# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Adapting the Snowflake Cortex LLM REST APIs to the LLMProvider interface.

Currently uses raw REST requests to act as the simplest, lowest-level reference.
An alternative would have been to use the Snowflake Python SDK as outlined in:
https://docs.snowflake.com/en/developer-guide/snowpark-ml/reference/1.8.1/index-cortex


WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import json
import re
import logging
import httpx
from typing import Dict, Any, List, Optional

from core.config import CONFIG
from llm_providers.llm_provider import LLMProvider
from retrieval_providers.utils import snowflake

logger = logging.getLogger(__name__)


class SnowflakeProvider(LLMProvider):
    """Implementation of LLMProvider for Snowflake LLM REST API calls."""

    @classmethod
    def get_client(cls):
        """No-op since no persistent client is needed."""
        return None

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
        Send an async chat completion request via snowflake.cortex.complete and return parsed JSON output.

        See: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-llm-rest-api#complete-function

        Arguments:
        - prompt: The prompt to complete
        - schema: JSON schema of the desired response.
        - model: The name of the model to use (if not specified, one will be chosen)
        - temperature: A value from 0 to 1 (inclusive) that controls the randomness of the output of the language model by influencing which possible token is chosen at each step.
        - max_tokens: A value between 1 and 4096 (inclusive) that controls the maximum number of tokens to output. Output is truncated after this number of tokens.
        - timeout: Maximum time (in seconds) to wait for a response.
        """
        return await cortex_complete(prompt, schema, model, max_tokens, temperature, timeout)


# Create a singleton instance
provider = SnowflakeProvider()


async def cortex_complete(
        prompt: str,
        schema: Dict[str, Any],
        model: str|None = None, 
        max_tokens: int = 4096, 
        temperature: float=0.0,
        timeout: float=60.0) -> str:
    """
    Send an async chat completion request via snowflake.cortex.complete and return parsed JSON output.

    See: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-llm-rest-api#complete-function

    Arguments:
    - prompt: The prompt to complete
    - schema: JSON schema of the desired response.
    - model: The name of the model to use (if not specified, one will be chosen)
    - max_tokens: A value between 1 and 4096 (inclusive) that controls the maximum number of tokens to output. Output is truncated after this number of tokens.
    - temperature: A value from 0 to 1 (inclusive) that controls the randomness of the output of the language model by influencing which possible token is chosen at each step.
    - timeout: Maximum time (in seconds) to wait for a response.
    """
    if model is None:
        model = "claude-3-5-sonnet"
    response = await post(
        "/api/v2/cortex/inference:complete",
        {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                # The precise system prompt may need adjustment given a model. For example, a simpler prompt worked well for larger
                # models but saying JSON twice helped for llama3.1-8b
                # Alternatively, should explore using structured outputs support as outlined in:
                # https://docs.snowflake.com/en/user-guide/snowflake-cortex/complete-structured-outputs
                {"role": "system", "content": f"Provide a response in valid JSON that matches this JSON schema: {json.dumps(schema)}"},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        },
        timeout,
    )
    try:
        return SnowflakeProvider.clean_response(response.get("choices")[0].get("message").get("content").strip())
    except Exception as e:
        logger.error(f"Error processing Snowflake response: {e}")
        return {}

async def post(api: str, request: dict, timeout: float) -> dict:
    cfg = CONFIG.llm_endpoints.get("snowflake")
    async with httpx.AsyncClient() as client:
        response =  await client.post(
            snowflake.get_account_url(cfg) + api,
            json=request,
            headers={
                    "Authorization": f"Bearer {snowflake.get_pat(cfg)}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
            },
            timeout=timeout,
        )
        if response.status_code == 400:
            logger.error(f"Snowflake API error: {response.json()}")
            return {}
        try:
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Snowflake API request failed: {e}")
            return {}
        return response.json()

