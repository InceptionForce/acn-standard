"""Dependency-light Python client SDK for ACN HTTP and A2A bindings."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .a2a import ACN_A2A_EXTENSION, ACN_MEDIA_TYPE
from .security import sign_agent_proof, sign_envelope


class AcnClientError(RuntimeError):
    """A typed remote ACN failure."""

    def __init__(self, status: int, code: str, detail: str, *, retryable: bool = False):
        self.status, self.code, self.detail = status, code, detail
        self.retryable = retryable
        super().__init__(detail)


@dataclass(frozen=True, slots=True)
class Submission:
    transaction_id: str
    message_id: str
    status: str
    duplicate: bool


def generate_ed25519_keypair() -> tuple[bytes, bytes]:
    """Return raw private/public Ed25519 key bytes suitable for secure storage."""
    private = Ed25519PrivateKey.generate()
    return (
        private.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        ),
        private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        ),
    )


def build_envelope(
    *,
    document_type: str,
    sender: str,
    recipient: str,
    document: dict[str, Any],
    transaction_id: str | None = None,
    message_id: str | None = None,
    idempotency_key: str | None = None,
    in_reply_to: str | None = None,
    expires_in: timedelta = timedelta(minutes=15),
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build an unsigned ACN 0.1 wire envelope with safe unique defaults."""
    created = now or datetime.now(UTC)
    value: dict[str, Any] = {
        "specVersion": "0.1",
        "messageId": message_id or f"msg_{uuid.uuid4().hex}",
        "transactionId": transaction_id or f"txn_{uuid.uuid4().hex}",
        "documentType": document_type,
        "sender": sender,
        "recipient": recipient,
        "createdAt": created.isoformat().replace("+00:00", "Z"),
        "expiresAt": (created + expires_in).isoformat().replace("+00:00", "Z"),
        "idempotencyKey": idempotency_key or str(uuid.uuid4()),
        "document": document,
    }
    if in_reply_to:
        value["inReplyTo"] = in_reply_to
    return value


class AcnClient:
    """Synchronous ACN client with bounded retries for transient failures."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30,
        retry_attempts: int = 2,
        retry_delay: float = 0.25,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        if not base_url.startswith("https://") and not base_url.startswith(
            "http://localhost"
        ):
            raise ValueError("ACN base URL must use HTTPS")
        self.base_url, self.timeout = base_url.rstrip("/"), timeout
        self.retry_attempts, self.retry_delay = max(0, retry_attempts), max(
            0, retry_delay
        )
        self._sleep = sleeper

    def _post(
        self, path: str, value: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any]:
        body = json.dumps(value, separators=(",", ":")).encode()
        for attempt in range(self.retry_attempts + 1):
            request = Request(
                self.base_url + path, data=body, headers=headers, method="POST"
            )
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    return json.load(response)
            except HTTPError as exc:
                retryable = exc.code in {429, 502, 503, 504}
                try:
                    problem = json.load(exc)
                except Exception:
                    problem = {}
                detail = (
                    problem.get("detail")
                    or problem.get("error", {}).get("message")
                    or "ACN request failed"
                )
                code = (
                    problem.get("code")
                    or problem.get("error", {}).get("status")
                    or "acn.http.error"
                )
                error = AcnClientError(exc.code, code, detail, retryable=retryable)
            except URLError as exc:
                error = AcnClientError(
                    0, "acn.transport.unavailable", str(exc.reason), retryable=True
                )
            if not error.retryable or attempt == self.retry_attempts:
                raise error
            self._sleep(self.retry_delay * (2**attempt))
        raise AssertionError("retry loop exhausted")

    def submit(self, envelope: dict[str, Any]) -> Submission:
        value = self._post(
            "/v1/messages",
            envelope,
            {"Content-Type": "application/json", "ACN-Version": "0.1"},
        )
        return Submission(
            value["transaction_id"],
            value["message_id"],
            value["status"],
            value["duplicate"],
        )

    def submit_a2a(self, envelope: dict[str, Any], message_id: str) -> Submission:
        request = {
            "message": {
                "messageId": message_id,
                "contextId": envelope["transactionId"],
                "role": "ROLE_USER",
                "parts": [{"mediaType": ACN_MEDIA_TYPE, "data": envelope}],
                "extensions": [ACN_A2A_EXTENSION],
            }
        }
        value = self._post(
            "/a2a/v1/message:send",
            request,
            {
                "Content-Type": "application/a2a+json",
                "A2A-Version": "1.0",
                "A2A-Extensions": ACN_A2A_EXTENSION,
            },
        )
        data = value["message"]["parts"][0]["data"]
        return Submission(
            data["transactionId"], data["messageId"], data["status"], data["duplicate"]
        )

    def claim_deliveries(self, proof: dict[str, str], *, limit: int = 10):
        return self._post(
            "/v1/delivery/claims", {"proof": proof, "limit": limit}, self._headers()
        )

    def acknowledge_delivery(
        self, delivery_id: str, proof: dict[str, str], *, lease_id: str
    ):
        """Acknowledge a claimed delivery.

        `lease_id` is the `leaseId` the claim returned. The proof must be signed
        over the operation `delivery.ack:{delivery_id}:{lease_id}`; a lease is
        what proves this caller still holds the delivery it is completing.
        """
        return self._post(
            f"/v1/delivery/{delivery_id}/ack",
            {"proof": proof, "leaseId": lease_id},
            self._headers(),
        )

    def reject_delivery(
        self, delivery_id: str, proof: dict[str, str], *, reason: str, lease_id: str
    ):
        """Return a delivery for redelivery. Proof operation is
        `delivery.reject:{delivery_id}:{lease_id}`."""
        return self._post(
            f"/v1/delivery/{delivery_id}/reject",
            {"proof": proof, "reason": reason, "leaseId": lease_id},
            self._headers(),
        )

    @staticmethod
    def _headers():
        return {"Content-Type": "application/json", "ACN-Version": "0.1"}


def signed_envelope(
    envelope: dict[str, Any], private_key: bytes, key_id: str
) -> dict[str, Any]:
    return sign_envelope(
        envelope, Ed25519PrivateKey.from_private_bytes(private_key), key_id
    )


def delivery_proof(
    *,
    operation: str,
    agent_id: str,
    key_id: str,
    private_key: bytes,
    timestamp: str,
    nonce: str | None = None,
) -> dict[str, str]:
    return sign_agent_proof(
        operation,
        agent_id,
        key_id,
        Ed25519PrivateKey.from_private_bytes(private_key),
        timestamp=timestamp,
        nonce=nonce or str(uuid.uuid4()),
    )
