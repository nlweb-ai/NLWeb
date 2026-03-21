#!/usr/bin/env python3
"""Standalone server that adapts NLWeb `/ask` responses to AppSDK format."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, Optional, List

from aiohttp import web
import aiohttp

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.utils.appsdk_adapter import (  # noqa: E402
    build_appsdk_error_response,
    convert_messages_to_appsdk_response,
)

logger = logging.getLogger(__name__)


def _normalize_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


class AppSDKAdapterServer:
    """HTTP server that proxies NLWeb `/ask` and wraps responses for AppSDK."""

    def __init__(self):
        self.host = os.environ.get("APPSDK_ADAPTER_HOST", "0.0.0.0")
        self.port = int(os.environ.get("APPSDK_ADAPTER_PORT", "8100"))
        base_url = os.environ.get("NLWEB_BASE_URL", "http://localhost:8000").rstrip("/")
        self.ask_url = f"{base_url}/ask"

    async def create_app(self) -> web.Application:
        app = web.Application()
        app["adapter"] = self
        app.on_startup.append(self.on_startup)
        app.on_cleanup.append(self.on_cleanup)
        app.router.add_get("/ask", self.handle_ask)
        app.router.add_post("/ask", self.handle_ask)
        return app

    async def on_startup(self, app: web.Application) -> None:
        timeout = aiohttp.ClientTimeout(total=60)
        app["client_session"] = aiohttp.ClientSession(timeout=timeout)
        logger.info("AppSDK adapter connected to NLWeb at %s", self.ask_url)

    async def on_cleanup(self, app: web.Application) -> None:
        session: aiohttp.ClientSession = app["client_session"]
        if not session.closed:
            await session.close()

    async def handle_ask(self, request: web.Request) -> web.Response:
        params = dict(request.query)

        json_body: Optional[Dict[str, Any]] = None
        data_body: Optional[Dict[str, Any]] = None

        if request.method == "POST" and request.can_read_body:
            if request.content_type == "application/json":
                json_body = await request.json()
            elif request.content_type == "application/x-www-form-urlencoded":
                form_data = await request.post()
                data_body = dict(form_data)
            else:
                message = f"Unsupported content type: {request.content_type}"
                payload = build_appsdk_error_response(message, status=415)
                return web.json_response(payload, status=415)

        use_streaming = self._resolve_streaming_choice(params, json_body, data_body)
        query_value = self._extract_query_value(params, json_body, data_body)

        self._apply_streaming_flag(use_streaming, params, json_body, data_body)

        forward_headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() not in {"host", "content-length"}
        }

        session: aiohttp.ClientSession = request.app["client_session"]
        try:
            if request.method == "GET":
                async with session.get(
                    self.ask_url, params=params, headers=forward_headers
                ) as upstream_response:
                    if use_streaming:
                        return await self._consume_stream(upstream_response, query_value)
                    return await self._transform_non_streaming(upstream_response, query_value)
            else:
                kwargs: Dict[str, Any] = {
                    "params": params,
                    "headers": forward_headers,
                }
                if json_body is not None:
                    kwargs["json"] = json_body
                elif data_body is not None:
                    kwargs["data"] = data_body

                async with session.post(self.ask_url, **kwargs) as upstream_response:
                    if use_streaming:
                        return await self._consume_stream(upstream_response, query_value)
                    return await self._transform_non_streaming(upstream_response, query_value)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Adapter error contacting NLWeb: %s", exc)
            payload = build_appsdk_error_response(str(exc), status=502)
            return web.json_response(payload, status=502)

    def _resolve_streaming_choice(
        self,
        params: Dict[str, Any],
        json_body: Optional[Dict[str, Any]],
        data_body: Optional[Dict[str, Any]],
    ) -> bool:
        if "streaming" in params:
            return _normalize_bool(str(params["streaming"]), default=True)

        if json_body and "streaming" in json_body:
            value = json_body["streaming"]
            if isinstance(value, bool):
                return value
            return _normalize_bool(str(value), default=True)

        if data_body and "streaming" in data_body:
            return _normalize_bool(str(data_body["streaming"]), default=True)

        return True

    def _apply_streaming_flag(
        self,
        use_streaming: bool,
        params: Dict[str, Any],
        json_body: Optional[Dict[str, Any]],
        data_body: Optional[Dict[str, Any]],
    ) -> None:
        params["streaming"] = "true" if use_streaming else "false"

        if json_body is not None:
            json_body["streaming"] = use_streaming
        if data_body is not None:
            data_body["streaming"] = "true" if use_streaming else "false"

    @staticmethod
    def _extract_query_value(
        params: Dict[str, Any],
        json_body: Optional[Dict[str, Any]],
        data_body: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        if json_body and isinstance(json_body.get("query"), str):
            return json_body["query"]
        if data_body and isinstance(data_body.get("query"), str):
            return data_body["query"]
        if isinstance(params.get("query"), str):
            return params["query"]
        return None

    async def _transform_non_streaming(
        self,
        response: aiohttp.ClientResponse,
        query: Optional[str],
    ) -> web.Response:
        status = response.status

        if status != 200:
            error_text = await response.text()
            payload = build_appsdk_error_response(error_text or response.reason, status=status)
            return web.json_response(payload, status=status)

        try:
            payload: Any = await response.json()
        except Exception:  # pylint: disable=broad-except
            error_text = await response.text()
            message = f"NLWeb returned non-JSON payload: {error_text[:200]}"
            payload = build_appsdk_error_response(message, status=502)
            return web.json_response(payload, status=502)

        if isinstance(payload, dict) and "structuredContent" in payload and "content" in payload:
            return web.json_response(payload)

        messages = self._extract_messages(payload)
        adapted = convert_messages_to_appsdk_response(messages, query=query, legacy_payload=payload)

        if isinstance(payload, dict) and payload:
            adapted["structuredContent"]["legacyResponse"] = payload

        return web.json_response(adapted)

    async def _consume_stream(
        self,
        response: aiohttp.ClientResponse,
        query: Optional[str],
    ) -> web.Response:
        status = response.status
        if status != 200:
            error_text = await response.text()
            payload = build_appsdk_error_response(error_text or response.reason, status=status)
            return web.json_response(payload, status=status)

        messages: List[Dict[str, Any]] = []
        partial_warning: Optional[str] = None
        stream_error: Optional[str] = None

        try:
            async for raw_line in response.content:
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line or line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    continue

                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break

                try:
                    message = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                messages.append(message)

                if message.get("message_type") == "error":
                    stream_error = message.get("error") or message.get("content")
                    if isinstance(stream_error, (dict, list)):
                        stream_error = json.dumps(stream_error)
                continue
        except Exception as exc:  # pylint: disable=broad-except
            stream_error = str(exc)

        if stream_error:
            partial_warning = f"Stream ended early: {stream_error}"

        if not messages and stream_error:
            payload = build_appsdk_error_response(stream_error, status=502)
            return web.json_response(payload, status=502)

        adapted = convert_messages_to_appsdk_response(
            messages,
            query=query,
            partial_warning=partial_warning,
        )
        return web.json_response(adapted)

    @staticmethod
    def _extract_messages(payload: Any) -> Any:
        if isinstance(payload, list):
            return payload

        if isinstance(payload, dict):
            if isinstance(payload.get("messages"), list):
                return payload["messages"]
            if isinstance(payload.get("content"), list):
                return payload["content"]

        return []

    async def start(self) -> None:
        app = await self.create_app()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        logger.info("AppSDK adapter listening on %s:%s", self.host, self.port)

        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass
        finally:
            await runner.cleanup()


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    server = AppSDKAdapterServer()
    await server.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
