#!/usr/bin/env python3
"""
Mock harness that calls NLWeb `/ask` (directly or via the adapter) and validates
the response against the OpenAI AppSDK tool shape.

Usage examples:

    python -m testing.mock_appsdk_tool --query "spicy crunchy snacks"
    python -m testing.mock_appsdk_tool --query "pizza" --base-url http://localhost:8000 --streaming
    python -m testing.mock_appsdk_tool --query "weather" --output output.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp

# Ensure project root is on sys.path when executed as a module/script
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.utils.appsdk_adapter import (  # noqa: E402
    convert_messages_to_appsdk_response,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mock AppSDK tool for NLWeb `/ask`.")
    parser.add_argument("--base-url", default="http://localhost:8100", help="NLWeb endpoint (adapter or core server).")
    parser.add_argument("--query", required=True, help="Query to send to NLWeb `/ask`.")
    parser.add_argument("--site", default=None, help="Optional site parameter.")
    parser.add_argument("--mode", default=None, help="Optional mode (list, summarize, generate).")
    parser.add_argument("--prev", nargs="*", default=None, help="Optional list of previous queries.")
    parser.add_argument("--streaming", action="store_true", help="Request streaming SSE/NDJSON response.")
    parser.add_argument("--non-streaming", action="store_true", help="Force streaming=false (default).")
    parser.add_argument("--method", choices=["get", "post"], default="get", help="HTTP method to use.")
    parser.add_argument("--output", default=None, help="Optional path to write AppSDK-formatted JSON.")
    return parser.parse_args()


async def fetch_streaming(
    session: aiohttp.ClientSession,
    url: str,
    params: Dict[str, Any],
    payload: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []

    request_kwargs: Dict[str, Any] = {"params": params}
    if payload is not None:
        request_kwargs["json"] = payload

    http_method = session.get if payload is None else session.post

    async with http_method(url, **request_kwargs) as response:
        response.raise_for_status()
        async for raw_line in response.content:
            line = raw_line.decode("utf-8", errors="ignore").strip()
            if not line or line.startswith(":") or not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break
            try:
                message = json.loads(data_str)
                messages.append(message)
            except json.JSONDecodeError:
                continue
    return messages


async def fetch_non_streaming(
    session: aiohttp.ClientSession,
    url: str,
    params: Dict[str, Any],
    payload: Optional[Dict[str, Any]],
) -> Any:
    request_kwargs: Dict[str, Any] = {"params": params}
    if payload is not None:
        request_kwargs["json"] = payload

    http_method = session.get if payload is None else session.post
    async with http_method(url, **request_kwargs) as response:
        response.raise_for_status()
        return await response.json()


def extract_messages(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        if isinstance(payload.get("messages"), list):
            return payload["messages"]
        if isinstance(payload.get("content"), list):
            return payload["content"]

    return []


async def run() -> Dict[str, Any]:
    args = parse_args()

    if args.streaming and args.non_streaming:
        raise SystemExit("Choose either --streaming or --non-streaming, not both.")

    streaming = False
    if args.streaming:
        streaming = True
    if args.non_streaming:
        streaming = False

    params: Dict[str, Any] = {"query": args.query}
    if args.site:
        params["site"] = args.site
    if args.mode:
        params["mode"] = args.mode
    if args.prev:
        params["prev"] = args.prev
    params["streaming"] = "true" if streaming else "false"

    payload: Optional[Dict[str, Any]] = None
    if args.method == "post":
        payload = {
            key: value
            for key, value in params.items()
            if key not in {"streaming"}
        }
        payload["streaming"] = streaming
        params = {}

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        url = args.base_url.rstrip("/") + "/ask"
        if streaming:
            messages = await fetch_streaming(session, url, params, payload)
            response_payload: Optional[Any] = None
        else:
            response_payload = await fetch_non_streaming(session, url, params, payload)
            messages = extract_messages(response_payload)

    adapted = convert_messages_to_appsdk_response(
        messages,
        query=args.query,
        partial_warning=None,
        legacy_payload=response_payload if isinstance(response_payload, dict) else None,
    )

    if response_payload and isinstance(response_payload, dict):
        adapted["structuredContent"]["legacyResponse"] = response_payload

    if args.output:
        Path(args.output).write_text(json.dumps(adapted, indent=2), encoding="utf-8")

    print(json.dumps(adapted, indent=2))
    return adapted


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
