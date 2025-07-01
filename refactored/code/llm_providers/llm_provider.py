# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Abstract base class for LLM providers.

This module defines the interface that all LLM providers must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    This class defines the interface that all LLM providers must implement
    to ensure consistent behavior across different implementations.
    """
    
    @abstractmethod
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
        Send a completion request to the LLM provider and return the parsed response.
        
        Args:
            prompt: The text prompt to send to the LLM
            schema: JSON schema that the response should conform to
            model: The specific model to use (if None, use default from config)
            temperature: Controls randomness of the output (0-1)
            max_tokens: Maximum tokens in the generated response
            timeout: Request timeout in seconds
            **kwargs: Additional provider-specific arguments
            
        Returns:
            Parsed JSON response from the LLM
            
        Raises:
            TimeoutError: If the request times out
            ValueError: If the response cannot be parsed or request fails
        """
        pass
    
    @classmethod
    @abstractmethod
    def get_client(cls):
        """
        Get or initialize the client for this provider.
        Returns a client instance ready to make API calls.
        
        Returns:
            A client instance configured for the provider
        """
        pass
    
    @classmethod
    @abstractmethod
    def clean_response(cls, content: str) -> Dict[str, Any]:
        """
        Clean and parse the raw response content into a structured dict.
        
        Args:
            content: Raw response content from the LLM
            
        Returns:
            Parsed JSON as a Python dictionary
            
        Raises:
            ValueError: If the content doesn't contain valid JSON
        """
        pass