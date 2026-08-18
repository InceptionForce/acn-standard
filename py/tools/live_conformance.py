#!/usr/bin/env python3
"""Probe a running ACN Cloud's public protocol and A2A conformance surface."""

from __future__ import annotations

import argparse
import base64
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from acn_standard import ACN_A2A_EXTENSION, verify_agent_card_signature


def get_json(url: str):
    with urlopen(url, timeout=10) as response:
        return (
            response.status,
            {key.lower(): value for key, value in response.headers.items()},
            json.load(response),
        )


def probe(base_url: str, public_key: bytes | None = None) -> dict:
    base = base_url.rstrip("/")
    results = []
    status, _, health = get_json(base + "/health")
    results.append(
        {"check": "health", "passed": status == 200 and health.get("status") == "ok"}
    )
    status, headers, discovery = get_json(base + "/.well-known/acn")
    results.append(
        {
            "check": "discovery",
            "passed": status == 200 and headers.get("acn-version") == "0.1",
        }
    )
    _, _, card = get_json(base + "/.well-known/agent-card.json")
    extension = card.get("capabilities", {}).get("extensions", [{}])[0].get("uri")
    results.append({"check": "a2a-card", "passed": extension == ACN_A2A_EXTENSION})
    if public_key:
        verify_agent_card_signature(card, public_key)
        results.append({"check": "a2a-card-signature", "passed": True})
    elif card.get("signatures"):
        _, _, jwks = get_json(base + "/.well-known/acn-jwks.json")
        key = jwks["keys"][0]
        raw = base64.urlsafe_b64decode(key["x"] + "=" * (-len(key["x"]) % 4))
        verify_agent_card_signature(card, raw, expected_key_id=key["kid"])
        results.append({"check": "a2a-card-signature", "passed": True})
    request = Request(
        base + "/v1/messages",
        data=b"{}",
        method="POST",
        headers={"Content-Type": "application/json", "ACN-Version": "9.0"},
    )
    try:
        urlopen(request, timeout=10)
        version_passed = False
    except HTTPError as exc:
        version_passed = (
            exc.code == 426 and json.load(exc).get("code") == "acn.version.unsupported"
        )
    results.append({"check": "version-negotiation", "passed": version_passed})
    return {"conformant": all(item["passed"] for item in results), "results": results}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--public-key", help="base64url raw Ed25519 public key")
    args = parser.parse_args()
    public_key = None
    if args.public_key:
        public_key = base64.urlsafe_b64decode(
            args.public_key + "=" * (-len(args.public_key) % 4)
        )
    result = probe(args.url, public_key)
    print(json.dumps(result, indent=2))
    return 0 if result["conformant"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
