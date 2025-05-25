# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Gemini (Google Vertex AI) embedding implementation.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import os
import asyncio
import threading
from typing import List, Optional

import vertexai
from vertexai.language_models import TextEmbeddingModel
from config.config import CONFIG

from utils.logging_config_helper import get_configured_logger, LogLevel
logger = get_configured_logger("gemini_embedding")

# Add lock for thread-safe initialization
_init_lock = threading.Lock()
_initialized = False

def get_gcp_project() -> str:
    """
    Retrieve the GCP project ID from configuration or environment.
    """
    # Get the project ID from the embedding provider config
    provider_config = CONFIG.get_embedding_provider("gemini")
    
    # For Gemini, we might need the GCP project ID
    if provider_config and provider_config.api_key:
        # The api_key field might actually store the project ID for GCP
        project = provider_config.api_key
        if project:
            return project
    
    # Fallback to environment variables
    project = os.getenv("GCP_PROJECT")
    if not project:
        error_msg = "GCP project ID not found in configuration or environment"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    return project

def get_gcp_location() -> str:
    """
    Retrieve the GCP location from configuration or environment.
    """
    # Check if endpoint in config contains location information
    provider_config = CONFIG.get_embedding_provider("gemini")
    if provider_config and provider_config.endpoint:
        # The endpoint might contain location information
        # Try to extract it if it follows a pattern like "us-central1-aiplatform.googleapis.com"
        parts = provider_config.endpoint.split('-')
        if len(parts) >= 2:
            location = f"{parts[0]}-{parts[1]}"
            return location
    
    # Fallback to environment or default
    return os.getenv("GCP_LOCATION", "us-central1")

def init_vertex_ai():
    """
    Initialize Vertex AI with project and location.
    """
    global _initialized
    with _init_lock:  # Thread-safe initialization
        if not _initialized:
            try:
                project = get_gcp_project()
                location = get_gcp_location()
                
                vertexai.init(
                    project=project,
                    location=location
                )
                _initialized = True
                logger.debug(f"Vertex AI initialized successfully with project: {project}, location: {location}")
            except Exception as e:
                logger.exception("Failed to initialize Vertex AI")
                raise

async def get_gemini_embeddings(
    text: str,
    model: Optional[str] = None,
    timeout: float = 30.0
) -> List[float]:
    """
    Generate an embedding for a single text using Vertex AI (Gemini).
    
    Args:
        text: The text to embed
        model: Optional model ID to use, defaults to provider's configured model
        timeout: Maximum time to wait for the embedding response in seconds
        
    Returns:
        List of floats representing the embedding vector
    """
    # If model not provided, get it from config
    if model is None:
        provider_config = CONFIG.get_embedding_provider("gemini")
        if provider_config and provider_config.model:
            model = provider_config.model
        else:
            # Default to a common Vertex AI embedding model
            model = "textembedding-gecko@003"
    
    logger.debug(f"Generating Gemini embedding with model: {model}")
    logger.debug(f"Text length: {len(text)} chars")
    
    # Ensure Vertex AI is initialized
    init_vertex_ai()
    
    try:
        # Use asyncio.to_thread to make the synchronous Vertex AI call non-blocking
        embedding_model = TextEmbeddingModel.from_pretrained(model)
        
        # Wrap the synchronous call in a thread to make it async
        response = await asyncio.to_thread(
            lambda: embedding_model.get_embeddings([text])
        )
        
        # Extract the embedding values from the response
        embedding = response[0].values
        logger.debug(f"Gemini embedding generated, dimension: {len(embedding)}")
        return embedding
    except Exception as e:
        logger.exception("Error generating Gemini embedding")
        logger.log_with_context(
            LogLevel.ERROR,
            "Gemini embedding generation failed",
            {
                "model": model,
                "text_length": len(text),
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        )
        raise

# Note: Gemini/Vertex AI might not support native batch embedding in the same way as OpenAI,
# so the main wrapper will handle batching by making multiple single embedding calls if needed.