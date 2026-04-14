# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Shared AWS Bedrock runtime client factory.

Single source of truth for boto3 bedrock-runtime client creation, used by
both the LLM provider (llm_providers/aws_bedrock.py) and the embedding
provider (embedding_providers/aws_bedrock_embedding.py).
"""

import os
import threading
from typing import Any

import boto3
from botocore.config import Config

from misc.logger.logging_config_helper import get_configured_logger

logger = get_configured_logger("aws_bedrock_client")

_client_lock = threading.Lock()
_client = None


def get_bedrock_runtime_client(timeout: float = 30.0) -> Any:
    """
    Return a singleton AWS Bedrock runtime client.

    max_pool_connections is set above the urllib3 default (10) to avoid
    "Connection pool is full" warnings when asyncio.gather fires many
    concurrent invoke_model calls in parallel.

    Args:
        timeout: Connect and read timeout in seconds (applied only on first initialization).

    Returns:
        boto3 bedrock-runtime client.
    """
    global _client
    with _client_lock:
        if _client is None:
            aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

            if not aws_access_key_id or not aws_secret_access_key:
                raise ValueError(
                    "AWS credentials not found. Set AWS_ACCESS_KEY_ID and "
                    "AWS_SECRET_ACCESS_KEY environment variables."
                )

            config = Config(
                connect_timeout=timeout,
                read_timeout=timeout,
                max_pool_connections=50,
            )
            _client = boto3.client(service_name="bedrock-runtime", config=config)
            logger.debug("AWS Bedrock runtime client initialized")

    return _client
