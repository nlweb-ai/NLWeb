# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
AWS Bedrock embedding implementation.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import json
import asyncio
from typing import List, Optional

from core.config import CONFIG
from llm_providers.aws_bedrock import AWSBedrockProvider

from misc.logger.logging_config_helper import get_configured_logger, LogLevel

logger = get_configured_logger("aws_bedrock_embedding")

# Cohere native batch limit per invoke_model call
_COHERE_BATCH_LIMIT = 96


def _build_embedding_body(model: str, text: str) -> dict:
    """
    Build the request body for a single-text embedding call based on the model family.

    Supported model families and their request formats:
    - amazon.titan-embed-text-*  → {"inputText": "..."}
    - amazon.titan-embed-image-* → {"inputText": "..."} (text-only path)
    - amazon.nova-*-embed-*      → nova-multimodal-embed-v1 schema
    - cohere.embed-*             → {"texts": ["..."], "input_type": "search_document"}
    - twelvelabs.marengo-*       → {"inputType": "text", "inputText": "..."}

    Ref: https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters.html
    """
    if model.startswith("amazon.titan-embed"):
        return {"inputText": text}

    elif model.startswith("amazon.nova") and "embed" in model:
        return {
            "schemaVersion": "nova-multimodal-embed-v1",
            "taskType": "SINGLE_EMBEDDING",
            "singleEmbeddingParams": {
                "text": {"value": text}
            },
        }

    elif model.startswith("cohere.embed"):
        return {
            "texts": [text],
            "input_type": "search_document",
        }

    elif model.startswith("twelvelabs.") or model.startswith("us.twelvelabs."):
        return {"inputType": "text", "inputText": text}

    raise ValueError(f"Embedding model '{model}' not supported")


def _parse_embedding_response(model: str, response_body: dict) -> List[float]:
    """
    Extract the embedding vector from the model response based on the model family.
    """
    try:
        if model.startswith("amazon.titan-embed"):
            return response_body["embedding"]
        elif model.startswith("amazon.nova") and "embed" in model:
            return response_body["embeddings"][0]["embedding"]
        elif model.startswith("cohere.embed"):
            return response_body["embeddings"][0]
        elif model.startswith("twelvelabs.") or model.startswith("us.twelvelabs."):
            return response_body["embedding"]
        else:
            raise ValueError(f"Model {model} not supported")
    except Exception as e:
        raise ValueError(f"Embedding model '{model}' not supported: {e}")


def _build_batch_embedding_body(model: str, texts: List[str]) -> dict:
    """
    Build the request body for a native batch embedding call.

    NOTE: Only Cohere Embed v3/v4 supports native batch via invoke_model (up to 96 texts).
    All other Bedrock embedding models accept a single text per call.
    Ref: https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-embed-v3.html
    """
    if model.startswith("cohere.embed"):
        return {
            "texts": texts,
            "input_type": "search_document",
        }

    raise ValueError(
        f"Model '{model}' does not support native batch embedding via invoke_model. "
        "Use concurrent single-text calls instead."
    )


def _parse_batch_embedding_response(model: str, response_body: dict) -> List[List[float]]:
    """
    Extract a list of embedding vectors from a native batch response (Cohere only).
    """
    if model.startswith("cohere.embed"):
        return response_body["embeddings"]

    raise ValueError(f"Model '{model}' does not support native batch embedding parsing")


async def get_aws_bedrock_embeddings(
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
    if model is None:
        provider_config = CONFIG.get_embedding_provider("aws_bedrock")
        if provider_config and provider_config.model:
            model = provider_config.model
        else:
            model = "amazon.titan-embed-text-v2:0"

    logger.debug(f"Generating AWS Bedrock embedding with model: {model}")
    logger.debug(f"Text length: {len(text)} chars")

    client = AWSBedrockProvider.get_client(timeout)

    try:
        text = text.replace("\n", " ")
        body = _build_embedding_body(model, text)

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.invoke_model(modelId=model, body=json.dumps(body)),
        )

        response_body = json.loads(response["body"].read())
        embedding = _parse_embedding_response(model, response_body)
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


async def get_aws_bedrock_batch_embeddings(
    texts: List[str], model: Optional[str] = None, timeout: float = 60.0
) -> List[List[float]]:
    """
    Generate embeddings for multiple texts using AWS Bedrock.

    Args:
        texts: List of texts to embed
        model: Optional model ID to use, defaults to provider's configured model
        timeout: Maximum time to wait for the embedding response in seconds

    Returns:
        List of embedding vectors, each a list of floats
    """
    if model is None:
        provider_config = CONFIG.get_embedding_provider("aws_bedrock")
        if provider_config and provider_config.model:
            model = provider_config.model
        else:
            model = "amazon.titan-embed-text-v2:0"

    logger.debug(f"Generating AWS Bedrock batch embeddings with model: {model}, count: {len(texts)}")

    if model.startswith("cohere.embed"):
        # Native batch: split into chunks and gather chunk calls.
        # Chunk size comes from config (batch_size); hard cap at _COHERE_BATCH_LIMIT (96).
        provider_config = CONFIG.get_embedding_provider("aws_bedrock")
        configured_batch_size = (provider_config.batch_size if provider_config and provider_config.batch_size else _COHERE_BATCH_LIMIT)
        chunk_size = min(configured_batch_size, _COHERE_BATCH_LIMIT)

        client = AWSBedrockProvider.get_client(timeout)
        loop = asyncio.get_event_loop()

        async def _invoke_chunk(chunk: List[str]) -> List[List[float]]:
            body = _build_batch_embedding_body(model, chunk)
            response = await loop.run_in_executor(
                None,
                lambda: client.invoke_model(modelId=model, body=json.dumps(body)),
            )
            response_body = json.loads(response["body"].read())
            return _parse_batch_embedding_response(model, response_body)

        chunks = [
            texts[i:i + chunk_size]
            for i in range(0, len(texts), chunk_size)
        ]
        chunk_results = await asyncio.gather(*[_invoke_chunk(chunk) for chunk in chunks])
        return [embedding for chunk in chunk_results for embedding in chunk]

    # For all other models (Titan, Nova, Marengo): concurrent single-text calls
    tasks = [get_aws_bedrock_embeddings(text, model=model, timeout=timeout) for text in texts]
    return list(await asyncio.gather(*tasks))
