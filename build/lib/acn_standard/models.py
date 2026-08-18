from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class CommerceEnvelope:
    spec_version: str
    message_id: str
    transaction_id: str
    document_type: str
    sender: str
    recipient: str
    created_at: datetime
    expires_at: datetime
    idempotency_key: str
    document: dict[str, Any]
    in_reply_to: str | None = None
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_wire(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "specVersion": self.spec_version,
            "messageId": self.message_id,
            "transactionId": self.transaction_id,
            "documentType": self.document_type,
            "sender": self.sender,
            "recipient": self.recipient,
            "createdAt": self.created_at.isoformat().replace("+00:00", "Z"),
            "expiresAt": self.expires_at.isoformat().replace("+00:00", "Z"),
            "idempotencyKey": self.idempotency_key,
            "document": self.document,
        }
        if self.in_reply_to:
            value["inReplyTo"] = self.in_reply_to
        if self.extensions:
            value["extensions"] = self.extensions
        return value
