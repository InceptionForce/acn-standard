# ACN Standard

> The canonical consolidated documentation is
> [ACN Standard 0.1 — final guide](FINAL-GUIDE.md).

ACN Standard is the open, transport-neutral commerce contract for Agent
Commerce Network. It defines what independent business agents exchange and
which commerce transitions are valid. It does not require ACN Cloud,
InceptionForce, Elorm, a particular agent framework or a particular transport.

Status: development draft `0.1.0`. The Ed25519 identity and signature profile
is implemented; irreversible financial execution still requires application
authorization, risk, approval and settlement controls.

## Scope

Version 0.1 implements the procurement-to-payment-intent slice:

```text
request_for_quote -> quotation -> quotation_acceptance -> approval_evidence
-> purchase_order -> order_acknowledgement -> fulfillment_status -> invoice
-> payment_intent -> payment_result -> settlement_confirmation
```

Disputes are an overlay and may be opened after an order exists without
destroying the underlying commercial state.

It defines a common envelope; stable identifiers; sender, recipient, expiry,
correlation and idempotency fields; exact decimal encoding; RFQ and quotation
documents; lifecycle rules; JSON Schemas; conformance fixtures; and a Python
reference validator.

It deliberately does not define business verification, discovery, marketplace
ranking, authorization policy, payment execution, settlement, managed
persistence, risk scoring, ERP behavior or connector implementation.

## Architecture

```text
                         ACN Standard
              Envelope · Documents · Lifecycles
                              │
             ┌────────────────┼────────────────┐
             │                │                │
             ▼                ▼                ▼
       Direct HTTP         A2A 1.0       ACN Cloud
       Agent ↔ Agent       binding        managed mode
             │                │                │
             └────────────────┼────────────────┘
                              ▼
                 Same commerce semantics
```

Transport bindings may carry ACN documents differently, but they must preserve
the envelope, document and lifecycle semantics.

Developers may use native ACN without A2A. Both native and A2A participants must
register their organization, agent, public signing key, and capabilities before
submitting commerce messages to managed ACN Cloud. See
[`specification/participation-and-transports.md`](specification/participation-and-transports.md)
for onboarding, endpoint selection, mixed-transport scenarios, and retry behavior.

HTTP implementations publish `GET /.well-known/acn`, accept the optional
`ACN-Version` request header, return the selected version on `/v1` responses,
and represent failures as `application/problem+json`. See
[`specification/versioning-and-errors.md`](specification/versioning-and-errors.md).

## Repository layout

```text
specification/
  overview.md                 scope and conformance language
  procurement-lifecycle.md    normative RFQ and quotation rules
schemas/
  common/envelope.schema.json
  identity/{organization,agent,credential}.schema.json
  procurement/request-for-quote.schema.json
  procurement/quotation.schema.json
  procurement/quotation-acceptance.schema.json
  procurement/approval-evidence.schema.json
  procurement/purchase-order.schema.json
  procurement/order-acknowledgement.schema.json
  procurement/fulfillment-status.schema.json
  procurement/invoice.schema.json
  procurement/payment-intent.schema.json
  payment/payment-result.schema.json
  payment/settlement-confirmation.schema.json
  disputes/dispute-opened.schema.json
  disputes/dispute-resolved.schema.json
conformance/
  valid/                      documents every implementation must accept
  invalid/                    documents every implementation must reject
src/acn_standard/
  models.py                   reference envelope model
  validation.py               reference semantic validator
  security.py                 canonicalization, signing and verification
tests/test_conformance.py
```

JSON Schemas are the wire-shape source of truth. The normative specification
defines cross-document and lifecycle behavior JSON Schema cannot express.

## Common envelope

```json
{
  "specVersion": "0.1",
  "messageId": "msg_rfq000001",
  "transactionId": "txn_purchase0001",
  "documentType": "request_for_quote",
  "sender": "agent:company-a:procurement",
  "recipient": "agent:company-b:sales",
  "createdAt": "2026-08-15T10:00:00Z",
  "expiresAt": "2026-08-16T10:00:00Z",
  "idempotencyKey": "company-a-rfq-1",
  "document": {}
}
```

| Field | Required | Meaning |
|---|---:|---|
| `specVersion` | Yes | ACN contract version; currently `0.1`. |
| `messageId` | Yes | Globally unique immutable message identifier. |
| `transactionId` | Yes | Stable identifier shared by the lifecycle. |
| `documentType` | Yes | Document schema and semantic behavior. |
| `sender` | Yes | Agent creating the document. |
| `recipient` | Yes | Intended receiving agent. |
| `createdAt` | Yes | Timezone-aware RFC 3339 creation time. |
| `expiresAt` | Yes | End of envelope validity. |
| `idempotencyKey` | Yes | Sender-scoped duplicate-submission key. |
| `inReplyTo` | Reply only | Message being answered. |
| `extensions` | No | Namespaced extension values. |
| `document` | Yes | Type-specific commerce document. |
| `signature` | Managed profile | Ed25519 key reference, timestamp and signature. |

The sender and recipient must differ. `expiresAt` must follow `createdAt`.
Unknown top-level fields are rejected. Extension keys must be namespaced, for
example `com.inceptionforce.approval-evidence`.

## Numeric representation

Quantities and money are JSON strings containing non-negative base-10 values:

```json
{
  "quantity": "500",
  "unitPrice": "85.00",
  "lineTotal": "42500.00"
}
```

JSON numbers such as `85.00`, scientific notation, negative zero, `NaN` and
infinity are invalid. Quantity and unit price support up to six decimal places;
monetary totals support up to two in version 0.1.

## Payload: request for quote

Company A needs 500 roofing sheets from Company B:

```json
{
  "specVersion": "0.1",
  "messageId": "msg_rfq000001",
  "transactionId": "txn_purchase0001",
  "documentType": "request_for_quote",
  "sender": "agent:company-a:procurement",
  "recipient": "agent:company-b:sales",
  "createdAt": "2026-08-15T10:00:00Z",
  "expiresAt": "2026-08-16T10:00:00Z",
  "idempotencyKey": "company-a-rfq-1",
  "document": {
    "currency": "GHS",
    "deliveryLocation": "Accra, GH",
    "responseDeadline": "2026-08-15T18:00:00Z",
    "items": [
      {
        "lineId": "line-1",
        "sku": "PPGL-0.45-BLUE",
        "description": "Blue 0.45mm PPGL roofing sheets",
        "quantity": "500",
        "unit": "sheet",
        "specifications": {
          "colour": "blue",
          "thicknessMm": "0.45"
        }
      }
    ]
  }
}
```

The RFQ must have at least one uniquely identified line. Quantities must be
positive and the response deadline must follow envelope creation.

## Payload: quotation

Company B responds:

```json
{
  "specVersion": "0.1",
  "messageId": "msg_quote00001",
  "transactionId": "txn_purchase0001",
  "documentType": "quotation",
  "sender": "agent:company-b:sales",
  "recipient": "agent:company-a:procurement",
  "createdAt": "2026-08-15T10:30:00Z",
  "expiresAt": "2026-08-16T10:30:00Z",
  "idempotencyKey": "company-b-quote-1",
  "inReplyTo": "msg_rfq000001",
  "document": {
    "currency": "GHS",
    "validUntil": "2026-08-16T08:00:00Z",
    "lines": [
      {
        "rfqLineId": "line-1",
        "quantity": "500",
        "unit": "sheet",
        "unitPrice": "85.00",
        "lineTotal": "42500.00"
      }
    ],
    "total": "42500.00",
    "paymentTerms": "30% deposit, balance on delivery",
    "deliveryTerms": "Delivered to Accra within 2 business days"
  }
}
```

The quotation reverses RFQ participants, retains its transaction ID, references
the RFQ message, retains currency, references existing RFQ lines, retains their
units, does not exceed requested quantities and has exact totals.

## Lifecycle flow

```text
Buyer                         Supplier
  │                              │
  │ request_for_quote            │
  ├─────────────────────────────►│
  │                              │ validate and price
  │ quotation                    │
  │◄─────────────────────────────┤
  │ validate references/totals   │
  ▼                              ▼
rfq_open                      quoted
```

Managed implementations may maintain transaction projections, but projections
are not wire documents and are not part of ACN Standard.

The extended payloads are executable examples under `conformance/valid/`:

| Document | Sender | Required relationship | Result |
|---|---|---|---|
| `quotation_acceptance` | Buyer | Chosen quotation | Locks one quotation |
| `quotation_counteroffer` | Buyer | Latest active quotation | Proposes revised commercial terms |
| `approval_evidence` | Buyer | Acceptance and policy | Approves or rejects spend |
| `purchase_order` | Buyer | Acceptance and quotation | Creates exact order |
| `order_acknowledgement` | Supplier | Purchase order | Accepts or rejects order |
| `transaction_cancellation` | Buyer | Latest pre-order message | Ends a pre-order transaction |
| `order_cancellation_request` | Either party | Latest order message | Requests bilateral cancellation |
| `order_cancellation_response` | Counterparty | Cancellation request | Accepts or rejects cancellation |
| `shipment_notice` | Supplier | Acknowledgement/latest receipt | Declares exact shipped line quantities |
| `goods_receipt` | Buyer | Latest shipment notice | Accepts/rejects every shipped quantity |
| `fulfillment_status` | Supplier | Order and prior status | Advances fulfillment |
| `invoice` | Supplier | Delivered order | Establishes amount due |
| `payment_intent` | Buyer | Invoice | Requests payment orchestration |
| `payment_result` | Supplier/payment agent | Intent | Records provider outcome |
| `settlement_confirmation` | Supplier/payment agent | Captured result | Records settlement outcome |
| `dispute_opened` | Either party | Challenged lifecycle message | Opens a case |
| `dispute_resolved` | Counterparty | Open dispute | Records resolution |

Each payment phase is distinct. Intent is not authorization, authorization is
not capture, and capture is not settlement. Applications must use the latest
explicit result rather than infer that money moved.

## Idempotency

The namespace is `(sender, idempotencyKey)`.

- Repeating the same key and payload returns the original outcome and must not
  create another business event.
- Repeating the key with a different payload must fail.
- A transport retry must not become a new commercial action.

Version 0.1 hashes compact JSON with sorted keys in the reference Cloud
implementation. The signed profile uses the same deterministic representation
with the top-level `signature` member omitted.

## Identity and signed-envelope profile

The registry hierarchy is `organization -> agent -> credential`. Credentials
contain Ed25519 public keys only; private keys stay with the agent. A signed
envelope adds:

```json
"signature": {
  "keyId": "key:company-a:2026-01",
  "algorithm": "Ed25519",
  "createdAt": "2026-08-16T12:00:00Z",
  "value": "<unpadded-base64url-Ed25519-signature>"
}
```

Verification binds the key to `sender`, checks the organization, agent and key
are active, enforces credential validity and clock skew, then verifies the
signature. Rotation registers a replacement key before revoking the old key.
See [specification/security-profile.md](specification/security-profile.md).

## Direct flow

```text
Buyer agent                    Supplier agent
    │ ACN envelope                   │
    ├───────────────────────────────►│
    │ quotation                      │
    │◄───────────────────────────────┤
```

Participants provide identity verification, authorization, delivery, audit and
recovery themselves.

## Managed flow

```text
Buyer agent        ACN Cloud         Supplier agent
    │ RFQ              │                  │
    ├─────────────────►│ validate/store   │
    │                  ├─────────────────►│
    │                  │ quotation        │
    │                  │◄─────────────────┤
    │◄─────────────────┤ validate/store   │
```

Cloud may provide identity, durable delivery, transaction projections, audit,
approval and recovery, but it cannot weaken Standard validation.

## Python reference use

```python
import json
from acn_standard import ContractError, validate_envelope

wire_value = json.loads(payload)
try:
    envelope = validate_envelope(wire_value)
except ContractError as exc:
    print(f"invalid ACN document: {exc}")
else:
    print(envelope.transaction_id)
```

Install and test:

```bash
python -m pip install -e ./acn-standard
cd acn-standard
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Conformance scenarios

Current checks cover valid RFQs and quotations, timezone-aware ordered times,
exact decimals, line and quotation totals, reply references, namespaced
extensions, unknown fields and invalid totals.

Every normative feature must add a valid or invalid fixture. A stable feature
requires two independent implementations to pass the same fixtures.

## Extensions

Experimental behavior belongs under `extensions`:

```json
{
  "extensions": {
    "com.inceptionforce.approval-evidence": {
      "approvalId": "approval_123"
    }
  }
}
```

Relays must preserve unknown extensions. Implementations may ignore an
extension unless participants negotiated it.

### Extensions a deployment may require

An extension is optional to the protocol but can be mandatory on a particular
network. The one you are most likely to meet is `acn.finance`, which ACN Cloud
requires on a `payment_intent` when its finance workflow is enabled:

```json
{
  "extensions": {
    "acn.finance": {
      "paymentRequestId": "payment-request:2f9c41a7b8d4"
    }
  }
}
```

The id refers to a payment request that people at the buying organization have
already approved. Without it such a deployment answers `409` — the document is
well formed and the network is simply not willing to move money that nobody
authorised. `conformance/valid/payment-intent-approved.json` is a complete
example; `payment-intent.json` is the same document without the extension, which
is valid protocol and is what a deployment without a finance workflow expects.

## Roadmap

```text
RFQ
 -> quotation
 -> counteroffer
 -> acceptance
 -> purchase order
 -> acknowledgement
 -> shipment notice
 -> goods receipt
 -> invoice
 -> payment status
```

Counteroffers, cancellation, partial fulfilment, the security profile, version
negotiation, error documents, and the A2A 1.0 binding are implemented. Before
stability, independent implementations must exercise the conformance suite and
the draft must complete governance review.

The A2A profile is specified in
[`specification/a2a-binding.md`](specification/a2a-binding.md).
[`specification/network-extension.md`](specification/network-extension.md) defines
the optional `acn.network` product-category and reservation-evidence contract.

## Developer tooling and releases

Install the Python package and run `acn-conformance validate envelope.json` or
`acn-conformance suite conformance/valid`. The package also exports `AcnClient`,
`build_envelope`, `signed_envelope`, and delivery proof helpers. A publishable,
zero-runtime-dependency TypeScript client lives in `../acn-sdk-typescript`.

Run `python tools/build_release.py` for a checksummed specification archive and
`python tools/generate_sbom.py` for the CycloneDX software bill of materials.
See `RELEASE.md`, `CHANGELOG.md`, and `COMPATIBILITY.md` for release policy.

See [GOVERNANCE.md](GOVERNANCE.md), [SECURITY.md](SECURITY.md) and
`specification/`.
