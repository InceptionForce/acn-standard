"""ACN 0.1 signed-envelope security profile."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .validation import ContractError


@dataclass(frozen=True, slots=True)
class EnvelopeSignature:
    key_id: str
    algorithm: str
    created_at: datetime
    value: bytes


def canonical_envelope(value: dict[str, Any]) -> bytes:
    """Return deterministic UTF-8 JSON excluding the signature itself."""
    unsigned = {key: item for key, item in value.items() if key != "signature"}
    return json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_agent_card(value: dict[str, Any]) -> bytes:
    """Canonicalize the ACN card profile for A2A JWS signing."""
    unsigned = {key: item for key, item in value.items() if key != "signatures"}
    return json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def sign_agent_card(
    value: dict[str, Any],
    private_key: Ed25519PrivateKey,
    key_id: str,
    *,
    jwks_url: str | None = None,
) -> dict[str, Any]:
    """Attach an RFC 7515 JWS signature following the A2A card profile."""
    header = {"alg": "EdDSA", "typ": "JOSE", "kid": key_id}
    if jwks_url:
        header["jku"] = jwks_url
    protected = _base64url(
        json.dumps(header, sort_keys=True, separators=(",", ":")).encode()
    )
    payload = _base64url(canonical_agent_card(value))
    signature = _base64url(private_key.sign(f"{protected}.{payload}".encode("ascii")))
    signed = dict(value)
    signed["signatures"] = [{"protected": protected, "signature": signature}]
    return signed


def verify_agent_card_signature(
    value: dict[str, Any], public_key: bytes, *, expected_key_id: str | None = None
) -> dict[str, Any]:
    """Verify the first supported EdDSA JWS signature and return its header."""
    signatures = value.get("signatures")
    if not isinstance(signatures, list) or not signatures:
        raise ContractError("Agent Card signature is required")
    signature = signatures[0]
    try:
        protected = signature["protected"]
        header = json.loads(
            base64.urlsafe_b64decode(protected + "=" * (-len(protected) % 4))
        )
        encoded = signature["signature"]
        raw_signature = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        payload = _base64url(canonical_agent_card(value))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ContractError("invalid Agent Card signature encoding") from exc
    if header.get("alg") != "EdDSA" or header.get("typ") != "JOSE":
        raise ContractError("unsupported Agent Card signature header")
    if expected_key_id and header.get("kid") != expected_key_id:
        raise ContractError("unexpected Agent Card signing key")
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            raw_signature, f"{protected}.{payload}".encode("ascii")
        )
    except (InvalidSignature, ValueError) as exc:
        raise ContractError("Agent Card signature verification failed") from exc
    return header


def sign_envelope(
    value: dict[str, Any], private_key: Ed25519PrivateKey, key_id: str
) -> dict[str, Any]:
    signed = dict(value)
    signed["signature"] = {
        "keyId": key_id,
        "algorithm": "Ed25519",
        "createdAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "value": base64.urlsafe_b64encode(private_key.sign(canonical_envelope(value)))
        .decode("ascii")
        .rstrip("="),
    }
    return signed


def parse_signature(value: dict[str, Any]) -> EnvelopeSignature:
    signature = value.get("signature")
    if not isinstance(signature, dict):
        raise ContractError("signature is required")
    if set(signature) != {"keyId", "algorithm", "createdAt", "value"}:
        raise ContractError("signature has invalid fields")
    if signature.get("algorithm") != "Ed25519":
        raise ContractError("unsupported signature algorithm")
    key_id = signature.get("keyId")
    if not isinstance(key_id, str) or not key_id.startswith("key:"):
        raise ContractError("invalid signature keyId")
    try:
        created_at = datetime.fromisoformat(
            signature["createdAt"].replace("Z", "+00:00")
        )
        encoded = signature["value"]
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (KeyError, TypeError, ValueError) as exc:
        raise ContractError("invalid signature encoding") from exc
    if created_at.tzinfo is None or len(raw) != 64:
        raise ContractError("invalid signature")
    return EnvelopeSignature(key_id, "Ed25519", created_at, raw)


def verify_envelope_signature(
    value: dict[str, Any], public_key: bytes
) -> EnvelopeSignature:
    signature = parse_signature(value)
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature.value, canonical_envelope(value)
        )
    except (InvalidSignature, ValueError) as exc:
        raise ContractError("signature verification failed") from exc
    return signature


def canonical_agent_proof(
    operation: str, agent_id: str, timestamp: str, nonce: str
) -> bytes:
    return f"acn-agent-proof-v1\n{operation}\n{agent_id}\n{timestamp}\n{nonce}".encode()


def sign_agent_proof(
    operation: str,
    agent_id: str,
    key_id: str,
    private_key: Ed25519PrivateKey,
    *,
    timestamp: str,
    nonce: str,
) -> dict[str, str]:
    signature = private_key.sign(
        canonical_agent_proof(operation, agent_id, timestamp, nonce)
    )
    return {
        "agentId": agent_id,
        "keyId": key_id,
        "timestamp": timestamp,
        "nonce": nonce,
        "signature": base64.urlsafe_b64encode(signature).decode().rstrip("="),
    }


def verify_agent_proof_signature(
    proof: dict[str, Any], operation: str, public_key: bytes
) -> None:
    try:
        encoded = proof["signature"]
        signature = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        payload = canonical_agent_proof(
            operation, proof["agentId"], proof["timestamp"], proof["nonce"]
        )
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, payload)
    except (KeyError, TypeError, ValueError, InvalidSignature) as exc:
        raise ContractError("agent proof verification failed") from exc
