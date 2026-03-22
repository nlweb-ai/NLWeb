"""
LLM abstraction layer with multi-provider fallback.

Tries providers in order until one succeeds:
1. Azure OpenAI (if AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY set)
2. Anthropic (if ANTHROPIC_API_KEY set)
3. OpenAI (if OPENAI_API_KEY set)
"""

import os
import json
from typing import Optional


def _try_azure_openai(system: str, user: str, temperature: float, max_tokens: int) -> Optional[str]:
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    key = os.environ.get("AZURE_OPENAI_API_KEY")
    if not endpoint or not key:
        return None
    try:
        from openai import AzureOpenAI
        client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=key,
            api_version="2024-12-01-preview",
        )
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"  Azure OpenAI failed: {e}")
        return None


def _try_anthropic(system: str, user: str, temperature: float, max_tokens: int) -> Optional[str]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text
    except Exception as e:
        print(f"  Anthropic failed: {e}")
        return None


def _try_openai(system: str, user: str, temperature: float, max_tokens: int) -> Optional[str]:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"  OpenAI failed: {e}")
        return None


PROVIDERS = [
    ("Azure OpenAI", _try_azure_openai),
    ("Anthropic", _try_anthropic),
    ("OpenAI", _try_openai),
]


def chat(system: str, user: str, temperature: float = 0, max_tokens: int = 2000) -> str:
    """Send a chat completion request, trying providers in order until one succeeds."""
    errors = []
    for name, fn in PROVIDERS:
        result = fn(system, user, temperature, max_tokens)
        if result is not None:
            return result
        errors.append(name)

    raise RuntimeError(
        f"All LLM providers failed or unconfigured. Tried: {', '.join(errors)}. "
        "Set one of: AZURE_OPENAI_ENDPOINT+AZURE_OPENAI_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY"
    )
