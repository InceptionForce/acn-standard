# ACN managed-network extension

`acn.network` is an optional, transport-neutral envelope extension. Native ACN HTTP
and the ACN A2A artifact binding carry the identical extension object.

```json
{
  "extensions": {
    "acn.network": {
      "productCategories": ["office-supplies/paper"],
      "reservationEvidence": {
        "reservationId": "reservation:01J...",
        "quotationMessageId": "msg_quote00001",
        "provider": "inventory.example",
        "expiresAt": "2026-08-16T12:00:00Z",
        "evidenceHash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
      }
    }
  }
}
```

`productCategories` contains at most 100 unique, normalized category identifiers.
Managed networks may require every category to be allowed by both the active partner
connection and the sender-owned federation policy.

`reservationEvidence` is permitted only on `purchase_order`. Its quotation must be
the quotation used by that order. A managed service may require the referenced
reservation to be active, unexpired and matched to the transaction, quotation,
provider and evidence hash. The extension is optional so direct ACN implementations
that do not support inventory reservations remain conformant.

Unknown namespaced extensions remain permitted under ACN's normal versioning rules.
