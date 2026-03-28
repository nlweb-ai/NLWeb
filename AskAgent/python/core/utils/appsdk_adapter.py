"""Adapters for transforming NLWeb responses into OpenAI AppSDK format."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _ensure_list(value: Any) -> List[Any]:
    """Return value as list, filtering out falsy entries."""
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if item is not None]
    return [value]


def _extract_answer_payload(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the answer payload (if any) from a message."""
    if not isinstance(message, dict):
        return None

    # handle Message schema (`content`) as well as legacy top-level fields
    payload = message.get("content")
    if isinstance(payload, dict) and "answer" in payload:
        return payload

    if message.get("answer"):
        payload = {key: message.get(key) for key in ("answer", "items", "@type") if key in message}
        return payload or None

    return None


def _collect_results(messages: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Collect result items and the message ids they originated from."""
    aggregated: List[Dict[str, Any]] = []
    origins: List[str] = []

    for message in messages:
        if not isinstance(message, dict):
            continue

        message_type = message.get("message_type")
        if message_type != "result":
            continue

        content = message.get("content")
        items = _ensure_list(content)
        if not items:
            continue

        aggregated.extend(items)
        origins.append(message.get("message_id", ""))

    return aggregated, origins


def _extract_legacy_results(legacy_payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pull result items from legacy payload structures."""
    if not isinstance(legacy_payload, dict):
        return []

    candidates: List[List[Dict[str, Any]]] = []

    # Direct results list
    top_results = legacy_payload.get("results")
    if isinstance(top_results, list):
        candidates.append(top_results)

    # structuredContent.{results}
    structured = legacy_payload.get("structuredContent") or legacy_payload.get("structured_content")
    if isinstance(structured, dict):
        sc_results = structured.get("results")
        if isinstance(sc_results, list):
            candidates.append(sc_results)

    merged: List[Dict[str, Any]] = []
    seen = set()
    for bucket in candidates:
        for item in bucket:
            key = _stable_repr(item)
            if key in seen:
                continue
            seen.add(key)
            merged.append(deepcopy(item))
    return merged


def convert_messages_to_appsdk_response(
    messages: List[Dict[str, Any]],
    query: Optional[str] = None,
    partial_warning: Optional[str] = None,
    legacy_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convert NLWeb message list into an AppSDK-compatible payload.

    The resulting object has the shape required by AppSDK tools:
    {
        "structuredContent": {...},
        "content": [{ "type": "text", "text": "..." }]
    }
    """
    if not isinstance(messages, list):
        messages = []

    # Collect details for structuredContent
    structured_messages = [
        message
        for message in deepcopy(messages)
        if not (
            isinstance(message, dict)
            and "content" in message
            and (message.get("content") is None or message.get("content") == "")
        )
    ]
    conversation_id = None

    for message in structured_messages:
        if isinstance(message, dict) and message.get("conversation_id"):
            conversation_id = message["conversation_id"]
            break

    aggregated_results, result_message_ids = _collect_results(structured_messages)
    legacy_results = _extract_legacy_results(legacy_payload)

    if legacy_results:
        if aggregated_results:
            existing_repr = {_stable_repr(item) for item in aggregated_results}
            for item in legacy_results:
                key = _stable_repr(item)
                if key not in existing_repr:
                    aggregated_results.append(item)
                    existing_repr.add(key)
        else:
            aggregated_results = legacy_results

    generated_answers: List[Dict[str, Any]] = []
    content_segments: List[Dict[str, Any]] = []

    for message in structured_messages:
        if not isinstance(message, dict):
            continue

        message_type = message.get("message_type")
        if message_type not in ("nlws", "answer", "GeneratedAnswer"):
            continue

        payload = _extract_answer_payload(message)
        if not payload:
            continue

        answer_text = payload.get("answer")
        if answer_text:
            generated_answers.append(
                {
                    "text": answer_text,
                    "messageId": message.get("message_id"),
                    "@type": payload.get("@type") or message.get("@type"),
                    "items": payload.get("items") or message.get("items"),
                }
            )
            content_segments.append({"type": "text", "text": answer_text})

    # Provide a fallback textual segment if we have no synthesized answer
    if not content_segments:
        if aggregated_results:
            visualizations = f"{len(aggregated_results)} visualization{'s' if len(aggregated_results) != 1 else ''}"
            if query:
                summary_text = f'Found {visualizations} for "{query}".'
            else:
                summary_text = f"Found {visualizations}."
        else:
            summary_text = "No results were returned."
        content_segments.append({"type": "text", "text": summary_text})

    if partial_warning:
        content_segments.append({"type": "text", "text": partial_warning})

    structured_content: Dict[str, Any] = {
        "messages": structured_messages,
        "results": aggregated_results,
        "metadata": {
            "resultMessageIds": [mid for mid in result_message_ids if mid],
            "messageCount": len(structured_messages),
        },
    }

    if query:
        structured_content["query"] = query

    if conversation_id:
        structured_content["conversationId"] = conversation_id

    if generated_answers:
        structured_content["generatedAnswers"] = generated_answers

    return {
        "structuredContent": structured_content,
        "content": content_segments,
    }


def build_appsdk_error_response(error_text: str, status: Optional[int] = None) -> Dict[str, Any]:
    """Create an AppSDK-compatible error payload."""
    structured_content: Dict[str, Any] = {
        "error": {
            "message": error_text,
        }
    }
    if status is not None:
        structured_content["error"]["status"] = status

    return {
        "structuredContent": structured_content,
        "content": [
            {"type": "text", "text": f"Error: {error_text}"},
        ],
    }
def _stable_repr(value: Any) -> str:
    """Generate a hashable representation for potentially nested data structures."""
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except TypeError:
        return repr(value)
