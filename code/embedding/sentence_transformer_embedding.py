# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
SentenceTransformer-based local embedding implementation.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import threading
from typing import List, Optional
import asyncio

from sentence_transformers import SentenceTransformer

from config.config import CONFIG
from utils.logging_config_helper import get_configured_logger, LogLevel

logger = get_configured_logger("sentence_transformer_embedding")

# Thread-safe singleton initialization
_model_lock = threading.Lock()
embedding_model = None

def get_model_name() -> str:
    """
    Retrieve the embedding model name from configuration or default.
    """
    provider_config = CONFIG.get_embedding_provider("sentence_transformers")
    if provider_config and provider_config.model:
        return provider_config.model
    return "all-MiniLM-L6-v2"  # Default lightweight model

def get_embedding_model(model_override: Optional[str] = None) -> SentenceTransformer:
    """
    Load and return a singleton SentenceTransformer model.
    """
    global embedding_model
    with _model_lock:
        if embedding_model is None:
            # Use override model if provided, otherwise use configured model
            model_name = model_override or get_model_name()
            try:
                embedding_model = SentenceTransformer(model_name)
                logger.info(f"Loaded SentenceTransformer model: {model_name}")
            except Exception as e:
                logger.exception(f"Failed to load SentenceTransformer model: {model_name}")
                raise
    return embedding_model

async def get_sentence_transformer_embedding(
    text: str,
    model: Optional[str] = None,
    timeout: float = 30.0
) -> List[float]:
    """
    Generate a single embedding using SentenceTransformer.

    Args:
        text: The input text to embed.
        model: Optional model name to override config.
        timeout: Unused, for compatibility.

    Returns:
        Embedding vector as list of floats.
    """
    try:
        model_instance = get_embedding_model(model)

        # Run the blocking encode operation in a thread pool
        loop = asyncio.get_running_loop()
        embedding = await loop.run_in_executor(
            None,
            lambda: model_instance.encode(text.replace("\n", " "), convert_to_numpy=True).tolist()
        )

        logger.debug(f"Generated embedding (dim={len(embedding)})")
        return embedding
    except Exception as e:
        logger.exception("Error generating SentenceTransformer embedding")
        raise

async def get_sentence_transformer_batch_embeddings(
    texts: List[str],
    model: Optional[str] = None,
    timeout: float = 60.0
) -> List[List[float]]:
    """
    Generate batch embeddings using SentenceTransformer.

    Args:
        texts: List of input texts.
        model: Optional model name to override config.
        timeout: Unused, for compatibility.

    Returns:
        List of embedding vectors.
    """
    try:
        model_instance = get_embedding_model()
        cleaned_texts = [t.replace("\n", " ") for t in texts]

        # Run the blocking encode operation in a thread pool
        loop = asyncio.get_running_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: model_instance.encode(cleaned_texts, convert_to_numpy=True).tolist()
        )

        logger.debug(f"Generated {len(embeddings)} embeddings (dim={len(embeddings[0])})")
        return embeddings
    except Exception as e:
        logger.exception("Error generating batch embeddings with SentenceTransformer")
        raise
