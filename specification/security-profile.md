# ACN 0.1 security profile

ACN agents use Ed25519 credentials registered against an active agent. The
private key never enters ACN Cloud. A sender signs the RFC 8785-inspired ACN
canonical form: UTF-8 JSON with sorted keys, compact separators, and the
top-level `signature` member omitted.

The signature contains `keyId`, `algorithm`, `createdAt`, and unpadded base64url
`value`. A verifier MUST ensure the organization, agent, and credential are
active; the key belongs to the envelope sender; the key is inside its validity
window; the signature time is close to server time; and the Ed25519 signature
is valid. Managed implementations additionally authorize the document type
against the agent's registered capabilities. Revocation takes effect on the
next registry read.

Key rotation adds a new credential before revoking the old one. Operators
SHOULD allow an overlap interval so in-flight messages can complete.

## Agent operation proofs

Non-envelope operations such as inbox claim and acknowledgement use a short
Ed25519 proof containing `agentId`, `keyId`, `timestamp`, `nonce`, and
`signature`. The signed bytes are:

```text
acn-agent-proof-v1\n<operation>\n<agentId>\n<timestamp>\n<nonce>
```

The operation binds the proof to one action and, for acknowledgement or
rejection, to the delivery and lease identifiers. Verifiers MUST enforce clock
skew and consume each agent-scoped nonce once. Nonces may be deleted after the
accepted timestamp window closes.
