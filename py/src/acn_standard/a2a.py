"""Normative ACN profile for A2A 1.0 JSON messages."""

from __future__ import annotations

from typing import Any

from .validation import ContractError, validate_envelope

ACN_A2A_EXTENSION = "https://spec.agentcommerce.network/extensions/commerce/v0.1"
ACN_MEDIA_TYPE = "application/vnd.acn+json"
ACN_RESULT_MEDIA_TYPE = "application/vnd.acn.result+json"


def parse_a2a_message(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - {"message", "metadata"}:
        raise ContractError("A2A SendMessage request has invalid fields")
    message = value.get("message")
    if not isinstance(message, dict):
        raise ContractError("A2A request requires message")
    allowed = {"messageId", "contextId", "role", "parts", "metadata", "extensions"}
    if set(message) - allowed or message.get("role") != "ROLE_USER":
        raise ContractError("A2A input message is invalid")
    message_id = message.get("messageId")
    if not isinstance(message_id, str) or not 1 <= len(message_id) <= 128:
        raise ContractError("A2A messageId is invalid")
    parts = message.get("parts")
    if not isinstance(parts, list) or len(parts) != 1:
        raise ContractError("A2A ACN message requires exactly one data part")
    part = parts[0]
    if (
        not isinstance(part, dict)
        or set(part) - {"data", "mediaType", "metadata"}
        or part.get("mediaType") != ACN_MEDIA_TYPE
        or not isinstance(part.get("data"), dict)
    ):
        raise ContractError(f"A2A part must contain {ACN_MEDIA_TYPE} structured data")
    envelope = validate_envelope(part["data"])
    context_id = message.get("contextId")
    if context_id is not None and context_id != envelope.transaction_id:
        raise ContractError("A2A contextId must equal the ACN transactionId")
    return part["data"]


def a2a_result_message(
    request: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    source = request["message"]
    return {
        "message": {
            "messageId": f"acn-result-{result['message_id']}",
            "contextId": result["transaction_id"],
            "role": "ROLE_AGENT",
            "parts": [
                {
                    "mediaType": ACN_RESULT_MEDIA_TYPE,
                    "data": {
                        "transactionId": result["transaction_id"],
                        "messageId": result["message_id"],
                        "status": result["status"],
                        "duplicate": result["duplicate"],
                    },
                }
            ],
            "metadata": {"inReplyTo": source["messageId"], "acnSpecVersion": "0.1"},
            "extensions": [ACN_A2A_EXTENSION],
        }
    }
