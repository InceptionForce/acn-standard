# ACN Standard 0.1 — final consolidated guide

This is the canonical implementation and integration guide for the open Agent
Commerce Network protocol. It consolidates architecture, participation, documents,
flows, scenarios, payloads, transports, security, conformance, versioning, and release
practice. ACN Cloud is documented separately; it is one optional implementation.

## 1. Purpose and boundary

ACN Standard defines how autonomous agents exchange signed commerce documents. It
does not provide an organization database, marketplace, KYC/KYB provider, payment
processor, inventory system, workflow queue, or hosted network.

An implementation may use ACN Standard:

- Directly between two agents.
- Through its own relay or gateway.
- Through ACN Cloud.
- As artifacts carried by an A2A 1.0 message.

No ACN Cloud registration is required for direct ACN or A2A use. Registration is
required only when consuming ACN Cloud managed-network services.

ACN Cloud currently manages externally running agent identities; it does not execute
developer agent code. The optional hosted-agent runtime is a future Cloud capability
and does not change ACN Standard.

## 2. Architecture

```text
Business agent
  ├── identity + Ed25519 key
  ├── ACN Standard SDK/validator
  ├── transaction state machine
  └── chosen transport
        ├── direct HTTPS
        ├── private relay
        ├── A2A 1.0 artifact
        └── ACN Cloud

ACN Standard
  ├── JSON Schemas
  ├── canonical envelope
  ├── signature/security profile
  ├── procurement lifecycle
  ├── transport bindings
  ├── extension rules
  └── conformance fixtures and CLI
```

The document is the protocol truth. A transport must not change its meaning.

## 3. Participants

An organization owns one or more agents. An agent has a stable identifier, declared
capabilities, and one or more time-bounded credentials.

```json
{
  "organizationId": "org:company-a",
  "displayName": "Company A"
}
```

```json
{
  "agentId": "agent:company-a:procurement",
  "organizationId": "org:company-a",
  "displayName": "Procurement Agent",
  "capabilities": ["procurement.rfq", "procurement.order"]
}
```

```json
{
  "keyId": "key:company-a:2026-01",
  "algorithm": "Ed25519",
  "publicKey": "<base64url-encoded-32-byte-public-key>",
  "notBefore": "2026-08-16T00:00:00Z",
  "expiresAt": "2027-08-16T00:00:00Z"
}
```

How identities are registered or discovered is deployment-specific. The standard
defines their interoperable representation and proof requirements.

## 4. Canonical envelope

Every commerce message uses this shape:

```json
{
  "specVersion": "0.1",
  "messageId": "msg_rfq000001",
  "transactionId": "txn_purchase0001",
  "documentType": "request_for_quote",
  "sender": "agent:company-a:procurement",
  "recipient": "agent:company-b:sales",
  "createdAt": "2026-08-16T10:00:00Z",
  "expiresAt": "2026-08-17T10:00:00Z",
  "idempotencyKey": "company-a-rfq-1",
  "document": {},
  "extensions": {},
  "signature": {
    "keyId": "key:company-a:2026-01",
    "algorithm": "Ed25519",
    "createdAt": "2026-08-16T10:00:00Z",
    "value": "<base64url-signature>"
  }
}
```

Rules:

- `messageId` identifies one immutable message.
- `transactionId` groups the full commercial lifecycle.
- `idempotencyKey` is unique within the sender's scope.
- `inReplyTo` is required where a document responds to another message.
- Decimal values are strings, never binary floating-point JSON numbers.
- Timestamps use RFC 3339 and an explicit offset, normally `Z`.
- Unknown top-level fields are rejected.
- Namespaced extensions must not change the meaning of standard fields.

## 5. Document types and actors

| Document | Normal sender | Purpose |
|---|---|---|
| `request_for_quote` | Buyer | Request price and delivery terms |
| `quotation` | Supplier | Offer priced lines and validity |
| `quotation_counteroffer` | Buyer | Negotiate a quotation |
| `quotation_acceptance` | Buyer | Select an active quotation |
| `approval_evidence` | Buyer | Record policy/human approval |
| `purchase_order` | Buyer | Create the binding order instruction |
| `order_acknowledgement` | Supplier | Accept or reject the order |
| `fulfillment_status` | Supplier | Report preparation progress |
| `shipment_notice` | Supplier | Declare shipped quantities |
| `goods_receipt` | Buyer | Accept/reject received quantities |
| `invoice` | Supplier | Invoice received/accepted quantities |
| `payment_intent` | Buyer | Declare an intended payment |
| `payment_result` | Payment agent | Report payment outcome |
| `settlement_confirmation` | Payment/settlement agent | Confirm final settlement |
| `transaction_cancellation` | Authorized participant | Cancel before an order exists |
| `order_cancellation_request` | Buyer or supplier | Request cancellation of an order |
| `order_cancellation_response` | Counterparty | Accept or reject cancellation |
| `dispute_opened` | Buyer or supplier | Open an auditable exception |
| `dispute_resolved` | Counterparty | Resolve the open dispute |
| `return_authorization` | Supplier | Authorize buyer-returned goods |
| `return_receipt` | Supplier | Confirm returned quantities |
| `credit_note` | Supplier | Credit accepted returned value |

The schemas in `schemas/` and validators in `src/acn_standard/validation.py` are
normative for the reference implementation.

## 6. End-to-end lifecycle

```text
RFQ
 -> quotation [-> counteroffer -> revised quotation]*
 -> quotation acceptance
 -> approval evidence
 -> purchase order
 -> order acknowledgement
 -> fulfillment updates
 -> shipment notice(s)
 -> goods receipt(s)
 -> invoice
 -> payment intent
 -> payment result
 -> settlement confirmation
```

Cancellation branches:

```text
Before purchase order: transaction_cancellation
After purchase order:  order_cancellation_request -> order_cancellation_response
```

Return branch:

```text
goods receipt/invoice
 -> dispute_opened by buyer
 -> return_authorization by supplier
 -> return_receipt by supplier
 -> credit_note by supplier
```

State transitions must verify actor direction, references, active quotation, totals,
quantities, currency, previous state, and duplicate use.

## 7. Core payload scenarios

### RFQ

```json
{
  "currency": "GHS",
  "deliveryLocation": "Accra, GH",
  "responseDeadline": "2026-08-16T18:00:00Z",
  "items": [{
    "lineId": "line-1",
    "sku": "PPGL-045-BLUE",
    "description": "Blue roofing sheets",
    "quantity": "500",
    "unit": "sheet",
    "specifications": {"thicknessMm": "0.45"}
  }]
}
```

### Quotation

```json
{
  "rfqMessageId": "msg_rfq000001",
  "currency": "GHS",
  "validUntil": "2026-08-16T17:00:00Z",
  "lines": [{
    "lineId": "line-1",
    "quantity": "500",
    "unit": "sheet",
    "unitPrice": "125.00",
    "lineTotal": "62500.00"
  }],
  "total": "62500.00"
}
```

### Purchase order

```json
{
  "quotationMessageId": "msg_quote00001",
  "approvalEvidenceMessageId": "msg_approval01",
  "orderNumber": "PO-2026-0001",
  "currency": "GHS",
  "lines": [{
    "lineId": "line-1",
    "quantity": "500",
    "unit": "sheet",
    "unitPrice": "125.00",
    "lineTotal": "62500.00"
  }],
  "total": "62500.00"
}
```

### Payment intent

```json
{
  "invoiceMessageId": "msg_invoice001",
  "currency": "GHS",
  "amount": "62500.00",
  "paymentReference": "PAY-2026-0001"
}
```

### Dispute and return

```json
{
  "disputeId": "dispute_00000001",
  "subjectMessageId": "msg_receipt001",
  "reason": "damaged_goods",
  "description": "Ten sheets were damaged in transit"
}
```

```json
{
  "disputeId": "dispute_00000001",
  "disputeMessageId": "msg_dispute001",
  "returnAuthorizationId": "return_auth_0001",
  "items": [{"lineId": "line-1", "quantity": "10", "unit": "sheet"}]
}
```

Complete valid and invalid payloads live in `conformance/`.

## 8. Security profile

1. Remove `signature` from the envelope.
2. Serialize canonical JSON with sorted keys and compact separators.
3. Sign the resulting bytes using Ed25519.
4. Encode the 64-byte signature with unpadded base64url.
5. The receiver resolves `keyId`, validates its owner and validity period, verifies
   the signature, checks sender capability and direction, rejects expired messages,
   and consumes replay/idempotency state atomically.

Agent operation proofs use the same canonical-signature principle for operations that
are not commerce envelopes. Private keys never belong in documents or logs.

Threat controls expected from a production implementation include TLS, clock-skew
bounds, replay ledgers, credential rotation/revocation, payload-size limits, rate
limits, safe webhook/connector networking, audit records, and secret-file support.

## 9. Transports and API conventions

ACN Standard is transport-neutral. The reference conventions are:

| Transport | Endpoint convention | Media type |
|---|---|---|
| Native managed/direct HTTP | `POST /v1/messages` | `application/acn+json` |
| A2A 1.0 | `POST /a2a/v1/message:send` | `application/a2a+json` |
| Webhook | Deployment-defined HTTPS URL | ACN event JSON |

Native HTTP returns an acceptance result containing transaction, message, state, and
duplicate status. A2A wraps the unchanged ACN envelope as an artifact using the ACN
extension URI. A mixed network can use native ACN on one side and A2A on the other;
the gateway must preserve the canonical envelope.

## 10. Extensions

Extension keys are reverse-domain-style names such as `acn.network` or
`com.example.tax`. Receivers may ignore unknown optional extensions. An extension
must not redefine amounts, actors, references, signatures, or lifecycle rules.

The optional `acn.network` extension carries product-category and quote-reservation
evidence. Managed federation and marketplace behavior remains outside the base
standard.

## 11. Errors and versioning

Clients send `ACN-Version: 0.1`. Unsupported versions should return an upgrade/error
response and advertise supported versions. Problem responses use stable machine codes,
human-readable details, correlation identifiers, and field-level violations where
available. Never parse business behavior from English error text.

Version `0.1` is a development contract. Backward-compatible additions may add
optional fields; breaking schema or lifecycle changes require a new version.

## 12. Reference SDK

```python
from acn_standard import validate_envelope, sign_envelope

validated = validate_envelope(envelope)
signed = sign_envelope(envelope, private_key, key_id="key:company-a:2026-01")
```

The SDK validates documents and security structures; it does not host identities,
deliver messages, or operate a marketplace.

## 13. Conformance and release

```bash
python -m unittest discover -s tests
acn validate conformance/valid/request-for-quote.json
acn conformance conformance
python tools/build_release.py
python tools/generate_sbom.py
```

A conforming implementation must accept valid fixtures, reject invalid fixtures,
preserve decimal precision, enforce references and actors, verify signatures, and
implement idempotent processing. Release artifacts include source/wheel archives,
checksums, compatibility notes, changelog, security policy, and SBOM.

## 14. Configuration

ACN Standard itself requires no server environment variables. Applications supply
keys, identity resolution, time, storage, transport, and policy through their own
configuration. Do not introduce ACN Cloud environment settings into portable clients.

## 15. Scenario selection

- Two known companies: direct ACN over mutually authenticated HTTPS.
- Existing A2A ecosystem: ACN envelope as an A2A artifact.
- Public discovery or managed trust: ACN Cloud marketplace and network.
- Private enterprise network: self-host the standard and organization services.
- Developer testing: reference SDK plus conformance fixtures.

The protocol remains the same in every scenario; only discovery, authorization,
delivery, persistence, and operations differ.

## 16. Source map

- `schemas/` — normative JSON schemas.
- `specification/` — detailed normative prose.
- `conformance/` — valid and invalid scenarios.
- `src/acn_standard/` — reference validation, security, SDK, A2A, and CLI.
- `SECURITY.md` — reporting and threat boundary.
- `GOVERNANCE.md` — change process.
- `COMPATIBILITY.md` — compatibility rules.
- `RELEASE.md` and `RELEASE-CANDIDATE.md` — release process/status.
