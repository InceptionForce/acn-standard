"""Typed optional ACN extension contracts."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from .validation import ContractError

ACN_NETWORK_EXTENSION = "acn.network"
_CATEGORY = re.compile(r"^[a-z0-9][a-z0-9._/-]{0,99}$")
_EVIDENCE_HASH = re.compile(r"^sha256:[a-fA-F0-9]{64}$")


def validate_network_extension(
    extensions: dict[str, Any], document_type: str
) -> dict[str, Any] | None:
    value = extensions.get(ACN_NETWORK_EXTENSION)
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {
        "productCategories",
        "reservationEvidence",
    }:
        raise ContractError("acn.network has invalid fields")
    categories = value.get("productCategories", [])
    if (
        not isinstance(categories, list)
        or len(categories) > 100
        or len(set(categories)) != len(categories)
    ):
        raise ContractError("acn.network.productCategories is invalid")
    if not all(
        isinstance(item, str) and _CATEGORY.fullmatch(item) for item in categories
    ):
        raise ContractError("acn.network.productCategories is invalid")
    evidence = value.get("reservationEvidence")
    if evidence is not None:
        if document_type != "purchase_order":
            raise ContractError("reservationEvidence is allowed only on purchase_order")
        required = {
            "reservationId",
            "quotationMessageId",
            "provider",
            "expiresAt",
            "evidenceHash",
        }
        if not isinstance(evidence, dict) or set(evidence) != required:
            raise ContractError("reservationEvidence has invalid fields")
        for field in ("reservationId", "provider"):
            if (
                not isinstance(evidence[field], str)
                or not 1 <= len(evidence[field]) <= 255
            ):
                raise ContractError(f"reservationEvidence.{field} is invalid")
        if not re.fullmatch(
            r"^msg_[A-Za-z0-9_-]{8,128}$", str(evidence["quotationMessageId"])
        ):
            raise ContractError("reservationEvidence.quotationMessageId is invalid")
        if not _EVIDENCE_HASH.fullmatch(str(evidence["evidenceHash"])):
            raise ContractError("reservationEvidence.evidenceHash is invalid")
        try:
            expires_at = datetime.fromisoformat(
                evidence["expiresAt"].replace("Z", "+00:00")
            )
        except (AttributeError, ValueError) as exc:
            raise ContractError("reservationEvidence.expiresAt is invalid") from exc
        if expires_at.tzinfo is None:
            raise ContractError("reservationEvidence.expiresAt must include a timezone")
    return value
