"""Unit tests for AppSDK adapter helpers."""

from pathlib import Path
import sys

PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from core.utils.appsdk_adapter import (  # noqa: E402
    build_appsdk_error_response,
    convert_messages_to_appsdk_response,
)


def test_convert_messages_with_answer():
    messages = [
        {
            "message_type": "result",
            "message_id": "msg#1",
            "conversation_id": "conv-123",
            "content": [
                {"@type": "Item", "name": "Alpha"},
                {"@type": "Item", "name": "Beta"},
            ],
        },
        {
            "message_type": "nlws",
            "message_id": "msg#2",
            "conversation_id": "conv-123",
            "content": {
                "@type": "GeneratedAnswer",
                "answer": "Here is what I found.",
                "items": [{"name": "Alpha"}],
            },
        },
    ]

    payload = convert_messages_to_appsdk_response(messages, query="snack ideas")

    assert payload["structuredContent"]["conversationId"] == "conv-123"
    assert len(payload["structuredContent"]["messages"]) == 2
    assert len(payload["structuredContent"]["results"]) == 2
    assert payload["structuredContent"]["query"] == "snack ideas"

    generated_answers = payload["structuredContent"].get("generatedAnswers")
    assert generated_answers is not None
    assert generated_answers[0]["text"] == "Here is what I found."

    assert payload["content"] == [{"type": "text", "text": "Here is what I found."}]


def test_convert_messages_without_answer_falls_back_to_summary():
    messages = [
        {
            "message_type": "result",
            "message_id": "msg#10",
            "content": {"@type": "Item", "name": "Solo"},
        }
    ]

    payload = convert_messages_to_appsdk_response(messages, query="solo result")

    assert payload["structuredContent"]["results"] == [{"@type": "Item", "name": "Solo"}]
    assert payload["content"] == [{"type": "text", "text": 'Found 1 visualization for "solo result".'}]


def test_messages_with_null_content_removed():
    messages = [
        {
            "message_type": "result",
            "message_id": "msg#1",
            "content": {"@type": "Item", "name": "Alpha"},
        },
        {
            "message_type": "status",
            "message_id": "msg#2",
            "content": None,
        },
        {
            "message_type": "status",
            "message_id": "msg#3",
            "content": "",
        },
    ]

    payload = convert_messages_to_appsdk_response(messages)

    structured = payload["structuredContent"]
    assert len(structured["messages"]) == 1
    assert structured["messages"][0]["message_id"] == "msg#1"
    assert structured["metadata"]["messageCount"] == 1


def test_legacy_results_are_used_when_messages_empty():
    legacy_payload = {
        "structuredContent": {
            "results": [
                {"@type": "Item", "name": "Legacy One"},
                {"@type": "Item", "name": "Legacy Two"},
            ]
        }
    }

    payload = convert_messages_to_appsdk_response(
        [],
        query="legacy",
        legacy_payload=legacy_payload,
    )

    assert payload["structuredContent"]["results"] == legacy_payload["structuredContent"]["results"]
    assert payload["content"] == [{"type": "text", "text": 'Found 2 visualizations for "legacy".'}]


def test_build_appsdk_error_response():
    payload = build_appsdk_error_response("Something went wrong", status=503)

    assert payload["structuredContent"]["error"]["message"] == "Something went wrong"
    assert payload["structuredContent"]["error"]["status"] == 503
    assert payload["content"] == [{"type": "text", "text": "Error: Something went wrong"}]


def test_partial_warning_appended_to_content():
    payload = convert_messages_to_appsdk_response(
        [],
        query="weather",
        partial_warning="Stream ended early; showing partial data.",
    )

    assert payload["structuredContent"]["results"] == []
    assert payload["content"] == [
        {"type": "text", "text": 'No results were returned.'},
        {"type": "text", "text": "Stream ended early; showing partial data."},
    ]
