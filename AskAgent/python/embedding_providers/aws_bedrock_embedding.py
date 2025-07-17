# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
OpenAI embedding implementation.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import os
import json
from typing import List, Optional, Any

from botocore.config import Config

import boto3
from core.config import CONFIG
import threading

from misc.logger.logging_config_helper import get_configured_logger, LogLevel

logger = get_configured_logger("aws_bedrock_embedding")

_client_lock = threading.Lock()
aws_bedrock_client = None


def get_aws_bedrock_api_key() -> str:
    """
    Retrieve the AWS Bedrock API key from configuration.
    """
    # Get the API key from the embedding provider config
    provider_config = CONFIG.get_embedding_provider("aws_bedrock")
    if provider_config and provider_config.api_key:
        api_key = provider_config.api_key
        if api_key:
            return api_key

    # Fallback to environment variable
    api_key = os.getenv("AWS_BEDROCK_API_KEY")
    if not api_key:
        error_msg = "AWS Bedrock API key not found in configuration or environment"
        logger.error(error_msg)
        raise ValueError(error_msg)

    return api_key


def get_aws_bedrock_region() -> str:
    """
    Retrieve the AWS Bedrock region from configuration.
    """
    # Get the API key from the embedding provider config
    provider_config = CONFIG.get_embedding_provider("aws_bedrock")
    if provider_config and provider_config.api_version:
        aws_region = provider_config.api_version
        if aws_region:
            return aws_region

    # Fallback to environment variable
    aws_region = os.getenv("AWS_BEDROCK_REGION")
    if not aws_region:
        error_msg = "AWS Bedrock region not found in configuration or environment"
        logger.error(error_msg)
        raise ValueError(error_msg)

    return aws_region


def get_runtime_client(timeout: float = 30.0) -> Any:
    """
    Configure and return an AWS Bedrock runtime client.
    """
    config = Config(connect_timeout=timeout, read_timeout=timeout)

    global aws_bedrock_client
    with _client_lock:
        if aws_bedrock_client is None:
            try:
                api_key = get_aws_bedrock_api_key()
                
                # Validate API key format
                parts = api_key.split(":")
                if len(parts) != 2:
                    error_msg = "AWS Bedrock API key must be in format 'access_key_id:secret_access_key'"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                    
                aws_access_key_id = parts[0]
                aws_secret_access_key = parts[1]
                aws_region = get_aws_bedrock_region()

                aws_bedrock_client = boto3.client(
                    service_name="bedrock-runtime",
                    region_name=aws_region,
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key,
                    config=config,
                )
                logger.debug("AWS Bedrock client initialized successfully")
            except Exception as e:
                logger.exception("Failed to initialize AWS Bedrock client")
                raise

    return aws_bedrock_client

def get_aws_bedrock_embeddings(
    text: str, model: Optional[str] = None, timeout: float = 30.0
) -> List[float]:
    """
    Generate an embedding for a single text using AWS Bedrock API.

    Args:
        text: The text to embed
        model: Optional model ID to use, defaults to provider's configured model
        timeout: Maximum time to wait for the embedding response in seconds

    Returns:
        List of floats representing the embedding vector
    """
    # If model not provided, get it from config
    if model is None:
        provider_config = CONFIG.get_embedding_provider("aws_bedrock")
        if provider_config and provider_config.model:
            model = provider_config.model
        else:
            # Default to a common embedding model
            model = "amazon.titan-embed-text-v2:0"

    logger.debug(f"Generating AWS Bedrock embedding with model: {model}")
    logger.debug(f"Text length: {len(text)} chars")

    client = get_runtime_client(timeout)

    try:
        # Clean input text (replace newlines with spaces)
        text = text.replace("\n", " ")

        response = client.invoke_model(
            modelId=model, body=json.dumps({"inputText": text})
        )

        model_response = json.loads(response["body"].read())
        embedding = model_response["embedding"]
        logger.debug(f"AWS Bedrock embedding generated, dimension: {len(embedding)}")
        return embedding
    except Exception as e:
        logger.exception("Error generating AWS Bedrock embedding")
        logger.log_with_context(
            LogLevel.ERROR,
            "AWS Bedrock embedding generation failed",
            {
                "model": model,
                "text_length": len(text),
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
        )
        raise
