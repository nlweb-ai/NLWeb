# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Adapting the Snowflake Cortex Embedding REST APIs to interfaces e

Currently uses raw REST requests to act as the simplest, lowest-level reference.
An alternative would have been to use the Snowflake Python SDK as outlined in:
https://docs.snowflake.com/en/developer-guide/snowpark-ml/reference/1.8.1/index-cortex


WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import logging
import httpx
from typing import List

from core.config import CONFIG
from core.utils import snowflake

logger = logging.getLogger(__name__)


async def cortex_embed(text: str, model: str|None = None) -> List[float]:
    """
    Embed text using snowflake.cortex.embed.

    See: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-llm-rest-api#label-cortex-llm-embed-function
    """
    cfg = CONFIG.get_embedding_provider("snowflake")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            snowflake.get_account_url(cfg) + "/api/v2/cortex/inference:embed",
            json={
                "text": [text], 
                "model": model or "snowflake-arctic-embed-m-v1.5"
            },
            headers={
                    "Authorization": f"Bearer {snowflake.get_pat(cfg)}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
            },
        )
        if response.status_code == 400:
            raise Exception(response.json())
        response.raise_for_status()
        return response.json().get("data")[0].get("embedding")[0]


async def get_snowflake_batch_embeddings(texts: List[str], model: str|None = None) -> List[List[float]]:
    """
    Embed multiple texts using snowflake.cortex.embed.
    
    Args:
        texts: List of texts to embed
        model: Optional model name, defaults to snowflake-arctic-embed-m-v1.5
        
    Returns:
        List of embedding vectors, each a list of floats
    """
    cfg = CONFIG.get_embedding_provider("snowflake")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            snowflake.get_account_url(cfg) + "/api/v2/cortex/inference:embed",
            json={
                "text": texts, 
                "model": model or "snowflake-arctic-embed-m-v1.5"
            },
            headers={
                    "Authorization": f"Bearer {snowflake.get_pat(cfg)}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
            },
        )
        if response.status_code == 400:
            raise Exception(response.json())
        response.raise_for_status()
        
        # Extract embeddings for all texts
        embeddings = []
        data = response.json().get("data")
        for item in data:
            embeddings.append(item.get("embedding")[0])
        
        return embeddings
