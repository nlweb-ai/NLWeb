# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
AWS Bedrock wrapper for LLM functionality.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import json
import re
from typing import Dict, Any, Optional

from botocore.exceptions import ReadTimeoutError, ConnectTimeoutError
from botocore.config import Config

import boto3
from core.config import CONFIG
import threading

from llm_providers.llm_provider import LLMProvider

from misc.logger.logging_config_helper import get_configured_logger

logger = get_configured_logger("llm")


class ConfigurationError(RuntimeError):
    """
    Raised when configuration is missing or invalid.
    """

    pass


class AWSBedrockProvider(LLMProvider):
    """Implementation of LLMProvider for AWS Bedrock."""

    _client_lock = threading.Lock()
    _client = None

    @classmethod
    def get_api_key(cls) -> str:
        """
        Retrieve the AWS Bedrock API key from environment or raise an error.
        """
        # Get the API key from aws bedrock config
        provider_config = CONFIG.llm_endpoints["aws_bedrock"]
        api_key = provider_config.api_key.split(":")[0]
        return api_key

    @classmethod
    def get_api_secret(cls) -> str:
        """
        Retrieve the AWS Bedrock API secret from environment or raise an error.
        """
        # Get the API secret from aws bedrock config
        provider_config = CONFIG.llm_endpoints["aws_bedrock"]
        api_secret = provider_config.api_key.split(":")[1]
        return api_secret

    @classmethod
    def get_api_region(cls) -> str:
        """
        Retrieve the AWS Bedrock API region from environment or raise an error.
        """
        # Get the API region from aws bedrock config
        provider_config = CONFIG.llm_endpoints["aws_bedrock"]
        api_region = provider_config.api_version
        return api_region

    @classmethod
    def get_client(cls, timeout: float = 30.0) -> boto3.client:
        """
        Configure and return an AWS Bedrock client.
        """
        config = Config(
            connect_timeout=timeout,
            read_timeout=timeout
        )

        with cls._client_lock:
            if cls._client is None:
                api_key = cls.get_api_key()
                api_secret = cls.get_api_secret()
                api_region = cls.get_api_region()
                cls._client = boto3.client(
                    service_name="bedrock-runtime",
                    region_name=api_region,
                    aws_access_key_id=api_key,
                    aws_secret_access_key=api_secret,
                    config=config
                )
        return cls._client

    @classmethod
    def _build_model_body(
        cls,
        model: str,
        prompt: str,
        schema: Dict[str, Any],
        max_tokens: int,
        temperature: float,
    ) -> Dict[str, Any]:
        """
        Construct the system and user message sequence enforcing a JSON schema.
        """
        formatted_prompt = f"Respond ONLY with a valid JSON and no other text that matches this schema: {json.dumps(schema, indent=2)}\n\nInstruction: {prompt}"
        if model.startswith("amazon.nova"):
            return {
                "system": [
                    {
                        "text": (
                            f"Provide a valid JSON response matching this schema: "
                            f"{json.dumps(schema)}"
                        )
                    }
                ],
                "messages": [
                    {"role": "user", "content": [{"text": prompt}]},
                ],
                "inferenceConfig": {
                    "maxTokens": max_tokens,
                    "temperature": temperature,
                },
            }
        elif model.startswith("amazon.titan-text"):
            return {
                "inputText": formatted_prompt,
                "textGenerationConfig": {
                    "maxTokenCount": max_tokens,
                    "temperature": temperature,
                },
            }
        elif model.startswith("ai21"):
            return {
                "prompt": formatted_prompt,
                "maxTokens": max_tokens,
                "temperature": temperature,
            }
        elif model.startswith("anthropic"):
            return {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [
                    {
                        "role": "system",
                        "content": {
                            "type": "text",
                            "text": (
                                f"Provide a valid JSON response matching this schema: "
                                f"{json.dumps(schema)}"
                            ),
                        },
                    },
                    {"role": "user", "content": {"type": "text", "text": prompt}},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        elif model.startswith("cohere.command-r"):
            return {
                "message": formatted_prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        elif model.startswith("cohere.command"):
            return {
                "prompt": formatted_prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        elif model.startswith("meta.llama3"):
            return {
                "prompt": formatted_prompt,
                "max_gen_len": max_tokens,
                "temperature": temperature,
            }
        elif model.startswith("mistral"):
            return {
                "prompt": f"<s>[INST] {formatted_prompt} [/INST]",
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        else:
            raise ValueError(f"Model {model} not supported")

    @classmethod
    def _get_response_by_model(cls, model: str, body: Dict[str, Any]) -> str:
        """
        Get the response from the model.
        """
        try:
            if model.startswith("amazon.nova"):
                return body["output"]["message"]["content"][0]["text"]
            elif model.startswith("amazon.titan-text"):
                return body["results"][0]["outputText"]
            elif model.startswith("ai21"):
                return body["completions"][0]["data"]["text"]
            elif model.startswith("anthropic"):
                return body["content"][0]["text"]
            elif model.startswith("cohere.command-r"):
                return body["text"]
            elif model.startswith("cohere.command"):
                return body["generations"][0]["text"]
            elif model.startswith("meta.llama3"):
                return body["generation"]
            elif model.startswith("mistral"):
                return body["outputs"][0]["text"]
            else:
                raise ValueError(f"Model {model} not supported")
        except Exception as e:
            raise ValueError(f"Error getting response from model {model}: {e}")

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
        temperature: float = 1.0,
        max_tokens: int = 2048,
        timeout: float = 30.0,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Send an async chat completion request to AWS Bedrock and return parsed JSON.
        """
        # If model not provided, get it from config
        if model is None:
            provider_config = CONFIG.llm_endpoints["aws_bedrock"]
            # Use the 'high' model for completions by default
            model = provider_config.models.high

        client = self.get_client(timeout)
        body = self._build_model_body(model, prompt, schema, max_tokens, temperature)

        try:
            # Run the synchronous boto3 client in a thread pool executor
            response = client.invoke_model(modelId=model, body=json.dumps(body))
        except ReadTimeoutError:
            logger.error("⏰ Read timeout: the model took too long to respond..")
            return {}
        except ConnectTimeoutError:
            logger.error("🚫 Completion request timed out after %s seconds.", timeout)
            return {}

        try:
            # Decode the response body.
            model_response = json.loads(response["body"].read())
            model_response_text = self._get_response_by_model(model, model_response)
            return self.clean_response(model_response_text)
        except Exception as e:
            logger.error(f"Error processing AWS Bedrock response: {e}")
            return {}


# Create a singleton instance
provider = AWSBedrockProvider()
