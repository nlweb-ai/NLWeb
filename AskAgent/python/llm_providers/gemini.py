# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Gemini wrapper for LLM functionality, using Google Developer API.
Reference: https://ai.google.dev/gemini-api/docs

WARNING: This code is under development and may undergo changes in future
releases. Backwards compatibility is not guaranteed at this time.
"""

import os
import json
import re
import logging
import asyncio
from typing import Dict, Any, Optional

import google.generativeai as genai 
from core.config import CONFIG
import threading

from llm_providers.llm_provider import LLMProvider
from misc.logger.logging_config_helper import get_configured_logger, LogLevel
logger = get_configured_logger("gemini")

# Suppress verbose AFC logging from Google GenAI
logging.getLogger("google_genai.models").setLevel(logging.WARNING)

class ConfigurationError(RuntimeError):
    """Raised when configuration is missing or invalid."""
    pass


class GeminiProvider(LLMProvider):
    """Implementation of LLMProvider for Google's Gemini API."""
    
    _initialized = False
    _client_lock = threading.Lock()

    @classmethod
    def get_api_key(cls) -> str:
        """Retrieve the API key for Gemini API."""
        provider_config = CONFIG.llm_endpoints["gemini"]
        if provider_config and provider_config.api_key:
            api_key = provider_config.api_key
            if api_key:
                api_key = api_key.strip('"')  # Remove quotes if present
                return api_key
        return None

    @classmethod
    def get_model_from_config(cls, high_tier=False) -> str:
        """Get the appropriate model from configuration based on tier."""
        provider_config = CONFIG.llm_endpoints.get("gemini")
        if provider_config and provider_config.models:
            model_name = provider_config.models.high if high_tier else provider_config.models.low
            if model_name:
                return model_name
        # Default values if not found
        # For free tier, use gemini-1.5-flash which is available without API key
        default_model = "gemini-1.5-flash" if not cls.get_api_key() else "gemini-2.0-flash"
        return default_model

    @classmethod
    def configure_gemini(cls):
        """Ensure Gemini API is configured."""
        with cls._client_lock:
            if not cls._initialized:
                api_key = cls.get_api_key()
                if not api_key:
                    # Try to use free tier without API key
                    logger.info("Gemini API key not found, attempting to use free tier")
                    try:
                        genai.configure()  # Configure without API key
                        cls._initialized = True
                        logger.info("Gemini configured with free tier (no API key)")
                    except Exception as e:
                        error_msg = f"Failed to configure Gemini without API key: {e}"
                        logger.error(error_msg)
                        raise ConfigurationError(error_msg)
                else:
                    genai.configure(api_key=api_key)
                    cls._initialized = True
                    logger.debug("Gemini configured successfully with API key")
        return True

    @classmethod
    def get_client(cls):
        """
        Implementation of abstract method from LLMProvider.
        For Gemini, we don't use a client object, just ensure configuration.
        """
        cls.configure_gemini()
        return None  # No client object needed for new Gemini API

    @classmethod
    def clean_response(cls, content: str) -> Dict[str, Any]:
        """
        Clean and extract JSON content from response text.
        """
        # Handle None content case
        if content is None:
            logger.warning("Received None content from Gemini API")
            return {}
            
        # Handle empty string case
        response_text = content.strip()
        if not response_text:
            logger.warning("Received empty content from Gemini API")
            return {}
            
        # Remove markdown code block indicators if present
        response_text = response_text.replace('```json', '').replace('```', '').strip()
                
        # Find the JSON object within the response
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        
        if start_idx == -1 or end_idx == 0:
            error_msg = "No valid JSON object found in response"
            logger.error(f"{error_msg}, content: {response_text}")
            return {}
            

        json_str = response_text[start_idx:end_idx]
                
        try:
            result = json.loads(json_str)

            # check if the value is a integer number, convert it to int
            for key, value in result.items():
                if isinstance(value, str) and re.match(r'^\d+$', value):
                    result[key] = int(value)
            return result
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse response as JSON: {e}"
            logger.error(f"{error_msg}, content: {json_str}")
            return {}

    async def get_completion(
        self,
        prompt: str,
        schema: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 20000,
        timeout: float = 60.0,
        high_tier: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Async chat completion using Google GenAI."""
        # If model not provided, get it from config
        model_to_use = model if model else self.get_model_from_config(high_tier)

        # Ensure Gemini is configured
        self.configure_gemini()

        system_prompt = f"""Provide a response that matches this JSON schema: {json.dumps(schema)}"""
        
        logger.debug(f"Sending completion request to Gemini API with model: {model_to_use}")
        
        # create the model
        model_instance = genai.GenerativeModel(
            model_to_use,
            system_instruction=system_prompt
        )

        config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            # "response_mime_type": "application/json",
        }
        # logger.debug(f"\t\tRequest config: {config}")
        # logger.debug(f"\t\tPrompt content: {prompt}...")  # Log first 100 chars
        try:
            print(f"\n=== GEMINI DEBUG ===")
            print(f"Model: {model_to_use}")
            print(f"Temperature: {temperature}")
            print(f"Timeout: {timeout} seconds")
            print(f"Prompt length: {len(prompt)} chars")
            print(f"First 200 chars of prompt: {prompt[:200]}...")
            
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: model_instance.generate_content(
                        prompt,
                        generation_config=config
                    )
                ),
                timeout=timeout
            )
            
            print(f"Response received: {response is not None}")
            if response:
                print(f"Has text attr: {hasattr(response, 'text')}")
                if hasattr(response, 'text'):
                    print(f"Text is not None: {response.text is not None}")
                    if response.text:
                        print(f"Text length: {len(response.text)}")
                        print(f"First 200 chars of response: {response.text[:200]}...")
                # Debug: print all attributes of response
                print(f"Response attributes: {dir(response)}")
                if hasattr(response, 'candidates'):
                    print(f"Candidates: {response.candidates}")
                    if response.candidates and len(response.candidates) > 0:
                        candidate = response.candidates[0]
                        print(f"First candidate content: {candidate.content}")
                        if candidate.content and hasattr(candidate.content, 'parts'):
                            print(f"Content parts: {candidate.content.parts}")
                            if candidate.content.parts:
                                for i, part in enumerate(candidate.content.parts):
                                    print(f"Part {i}: {part}")
                        print(f"Finish reason: {candidate.finish_reason if hasattr(candidate, 'finish_reason') else 'N/A'}")
                if hasattr(response, 'prompt_feedback'):
                    print(f"Prompt feedback: {response.prompt_feedback}")
            
            # Try to extract text from response or candidates
            content = None
            if response:
                # First try the text attribute
                if hasattr(response, 'text') and response.text:
                    content = response.text
                # If text is empty, try to extract from candidates
                elif hasattr(response, 'candidates') and response.candidates:
                    for candidate in response.candidates:
                        if candidate.content and hasattr(candidate.content, 'parts') and candidate.content.parts:
                            # Extract text from parts
                            text_parts = []
                            for part in candidate.content.parts:
                                if hasattr(part, 'text'):
                                    text_parts.append(part.text)
                                elif isinstance(part, str):
                                    text_parts.append(part)
                            if text_parts:
                                content = ' '.join(text_parts)
                                break
            
            if not content:
                logger.error("Invalid or empty response from Gemini - no content extracted")
                print("=== END GEMINI DEBUG (ERROR) ===\n")
                # Return empty dict with score 0 for WHO ranking
                return {"score": 0, "description": "Failed to get response from Gemini"}
            
            logger.debug("Received response from Gemini API")
            logger.debug(f"\t\tResponse content: {content[:100]}...")  # Log first 100 chars
            print(f"Extracted content length: {len(content)}")
            print(f"First 200 chars of extracted content: {content[:200]}...")
            print("=== END GEMINI DEBUG (SUCCESS) ===\n")
            return self.clean_response(content)
        except asyncio.TimeoutError:
            logger.error(
                "Gemini completion request timed out after %s seconds", timeout
            )
            return {}
        except Exception as e:
            logger.error(
                f"Gemini completion failed: {type(e).__name__}: {str(e)}"
            )
            raise


# Create a singleton instance
provider = GeminiProvider()

# For backwards compatibility
get_gemini_completion = provider.get_completion
