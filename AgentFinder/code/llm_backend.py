"""
Swappable LLM/embedding backend interface.
Implement LLMBackend class for your provider (Azure OpenAI, OpenAI, Anthropic, etc.)
"""
import os
import json
import asyncio
import itertools
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

# Configuration from environment variables
LLM_CONFIG = {
    "provider": os.getenv("LLM_PROVIDER", "azure_openai"),  # azure_openai, openai, anthropic
    "endpoint": os.getenv("LLM_ENDPOINT"),  # Must be set via environment variable
    "api_key": os.getenv("LLM_API_KEY"),  # Must be set via environment variable
    "model": os.getenv("LLM_MODEL", "gpt-4"),
    "embedding_model": os.getenv("LLM_EMBEDDING_MODEL", "text-embedding-3-large"),
    "max_concurrent": int(os.getenv("LLM_MAX_CONCURRENT", "25")),
    "api_version": os.getenv("LLM_API_VERSION", "2024-02-01"),
}


class LLMBackend(ABC):
    """Abstract base for LLM backends"""

    @abstractmethod
    async def initialize(self):
        """Initialize clients and connection pools"""
        pass

    @abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for text"""
        pass

    @abstractmethod
    async def rank_site(self, query: str, site_json: str) -> Dict[str, Any]:
        """
        Rank a site for a query.
        Returns: {"score": int, "description": str}
        """
        pass

    @abstractmethod
    async def close(self):
        """Cleanup connections"""
        pass


class AzureOpenAIBackend(LLMBackend):
    """Azure OpenAI implementation"""

    def __init__(self):
        self.clients = []
        self.client_cycle = None
        self.semaphore = asyncio.Semaphore(LLM_CONFIG["max_concurrent"])

    async def initialize(self):
        """Initialize Azure OpenAI clients with connection pooling"""
        from openai import AsyncAzureOpenAI

        # Validate required configuration
        if not LLM_CONFIG["endpoint"]:
            raise ValueError(
                "LLM_ENDPOINT environment variable is required. "
                "Please set it to your Azure OpenAI endpoint URL (e.g., https://your-openai.openai.azure.com)"
            )

        if not LLM_CONFIG["api_key"]:
            raise ValueError(
                "LLM_API_KEY environment variable is required. "
                "Please set it to your Azure OpenAI API key"
            )

        # Create pool of clients for parallel calls
        num_clients = min(5, LLM_CONFIG["max_concurrent"] // 5)
        for i in range(num_clients):
            client = AsyncAzureOpenAI(
                azure_endpoint=LLM_CONFIG["endpoint"],
                api_key=LLM_CONFIG["api_key"],
                api_version=LLM_CONFIG["api_version"],
                max_retries=1,
                timeout=10.0
            )
            self.clients.append(client)

        # Create round-robin client selector
        self.client_cycle = itertools.cycle(self.clients)

        print(f"Azure OpenAI initialized with {len(self.clients)} clients, max {LLM_CONFIG['max_concurrent']} concurrent calls")

    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding vector from Azure OpenAI"""
        client = next(self.client_cycle)

        try:
            response = await client.embeddings.create(
                model=LLM_CONFIG["embedding_model"],
                input=text[:8000]  # Limit input length
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Embedding error: {e}")
            # Return zero vector on error (will rank low)
            return [0.0] * 1536  # Default embedding size

    async def rank_site(self, query: str, site_json: str) -> Dict[str, Any]:
        """Rank a site using Azure OpenAI"""
        async with self.semaphore:
            client = next(self.client_cycle)

            prompt = f"""Assign a score between 0 and 100 to the following site based on the likelihood that the site will contain an answer to the user's question.

First think about the kind of thing the user is seeking and then verify that the site is primarily focused on that kind of thing.

If the user is looking to buy a product, the site should sell the product, not just have useful information.
If the user is looking for information, the site should focus on that kind of information.

The user's question is: {query}

The site's description is:
{site_json}

Return JSON only with this exact format: {{"score": <integer 0-100>, "description": "<one sentence explanation>"}}"""

            try:
                response = await client.chat.completions.create(
                    model=LLM_CONFIG["model"],
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0,
                    max_tokens=100
                )

                result = json.loads(response.choices[0].message.content)

                # Ensure required fields
                if "score" not in result:
                    result["score"] = 0
                if "description" not in result:
                    result["description"] = "No description provided"

                # Ensure score is an integer between 0 and 100
                result["score"] = max(0, min(100, int(result["score"])))

                return result

            except Exception as e:
                print(f"Ranking error: {e}")
                return {"score": 0, "description": f"Error: {str(e)[:100]}"}

    async def close(self):
        """Cleanup - OpenAI clients don't need explicit cleanup"""
        pass


class OpenAIBackend(LLMBackend):
    """OpenAI (non-Azure) implementation"""

    def __init__(self):
        self.clients = []
        self.client_cycle = None
        self.semaphore = asyncio.Semaphore(LLM_CONFIG["max_concurrent"])

    async def initialize(self):
        """Initialize OpenAI clients"""
        from openai import AsyncOpenAI

        # Create pool of clients
        num_clients = min(5, LLM_CONFIG["max_concurrent"] // 5)
        for i in range(num_clients):
            client = AsyncOpenAI(
                api_key=LLM_CONFIG["api_key"],
                max_retries=1,
                timeout=10.0
            )
            self.clients.append(client)

        self.client_cycle = itertools.cycle(self.clients)
        print(f"OpenAI initialized with {len(self.clients)} clients")

    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding from OpenAI"""
        client = next(self.client_cycle)

        try:
            response = await client.embeddings.create(
                model=LLM_CONFIG["embedding_model"],
                input=text[:8000]
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Embedding error: {e}")
            return [0.0] * 1536

    async def rank_site(self, query: str, site_json: str) -> Dict[str, Any]:
        """Rank a site using OpenAI"""
        async with self.semaphore:
            client = next(self.client_cycle)

            prompt = f"""Assign a score between 0 and 100 to the following site based on the likelihood that the site will contain an answer to the user's question.

The user's question is: {query}

The site's description is:
{site_json}

Return JSON only: {{"score": <0-100>, "description": "<brief reason>"}}"""

            try:
                response = await client.chat.completions.create(
                    model=LLM_CONFIG["model"],
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0,
                    max_tokens=100
                )

                result = json.loads(response.choices[0].message.content)
                result["score"] = max(0, min(100, int(result.get("score", 0))))
                if "description" not in result:
                    result["description"] = "No description"

                return result

            except Exception as e:
                print(f"Ranking error: {e}")
                return {"score": 0, "description": f"Error: {str(e)[:100]}"}

    async def close(self):
        """Cleanup"""
        pass


class AnthropicBackend(LLMBackend):
    """Anthropic Claude implementation (placeholder)"""

    def __init__(self):
        self.client = None
        self.semaphore = asyncio.Semaphore(LLM_CONFIG["max_concurrent"])

    async def initialize(self):
        """Initialize Anthropic client"""
        # Example implementation
        # from anthropic import AsyncAnthropic
        # self.client = AsyncAnthropic(api_key=LLM_CONFIG["api_key"])
        raise NotImplementedError("Anthropic backend not yet implemented")

    async def get_embedding(self, text: str) -> List[float]:
        """Anthropic doesn't provide embeddings - would need a separate service"""
        raise NotImplementedError("Anthropic doesn't provide embeddings - use OpenAI for embeddings")

    async def rank_site(self, query: str, site_json: str) -> Dict[str, Any]:
        """Rank using Claude"""
        raise NotImplementedError("Anthropic backend not yet implemented")

    async def close(self):
        """Cleanup"""
        pass


# Factory function
def get_llm_backend() -> LLMBackend:
    """Get the configured LLM backend"""
    provider = LLM_CONFIG["provider"].lower()

    if provider == "azure_openai":
        return AzureOpenAIBackend()
    elif provider == "openai":
        return OpenAIBackend()
    elif provider == "anthropic":
        return AnthropicBackend()
    else:
        raise ValueError(f"Unknown LLM provider: {LLM_CONFIG['provider']}")