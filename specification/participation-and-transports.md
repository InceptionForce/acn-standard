# Participation, onboarding, and transport selection

ACN is an independent commerce protocol. A2A is an optional interoperability
binding, not a prerequisite for using ACN.

## Participation model

An unknown client may read ACN discovery and the public A2A Agent Card, but it
may not create commerce state. A participating company or developer must:

1. Register an organization with ACN Cloud.
2. Register one or more agents owned by that organization.
3. Register each agent's Ed25519 public key.
4. Assign only the commerce document capabilities the agent requires.
5. Keep the private key outside ACN Cloud and sign every ACN envelope.

ACN Cloud verifies organization and agent status, credential revocation,
signature freshness and validity, sender ownership, capabilities, governance,
schema validity, lifecycle state, and idempotency before accepting a message.

## Native ACN client

A backend, ERP, marketplace, payment service, or custom application can send a
signed ACN envelope directly:

```http
POST /v1/messages
Content-Type: application/json
ACN-Version: 0.1
```

This is the simplest binding and does not require an A2A framework.

## A2A-compatible agent

An A2A agent discovers `/.well-known/agent-card.json`, verifies its JWS through
`/.well-known/acn-jwks.json`, then wraps the same signed ACN envelope in an A2A
message:

```http
POST /a2a/v1/message:send
Content-Type: application/a2a+json
A2A-Version: 1.0
A2A-Extensions: https://agentcommerce.network/extensions/commerce/v0.1
```

Registration is still required. A2A provides discovery, framing, and transport;
it does not grant authorization to transact on ACN.

## Mixed transaction scenario

One commerce transaction can safely mix transports:

```text
Buyer application  -- /v1/messages ----------> request_for_quote
Supplier A2A agent -- /a2a/v1/message:send ---> quotation
Buyer application  -- /v1/messages ----------> purchase_order
Logistics A2A agent /a2a/v1/message:send -----> shipment_notice
ERP connector      -- /v1/messages ----------> goods_receipt and invoice
Payment A2A agent  -- /a2a/v1/message:send ---> payment_result
```

Both endpoints use the same identity checks, MongoDB transaction engine,
lifecycle rules, audit chain, delivery inbox, connector jobs, and idempotency
ledger. Retrying the same envelope through another binding does not create a
second commerce operation.

## Selection rule

Use `/v1/messages` for ACN-native software and system connectors. Use
`/a2a/v1/message:send` when the participant already uses A2A discovery and
messaging. The choice changes the outer transport, not ACN commerce semantics.
