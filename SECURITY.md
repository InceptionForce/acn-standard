# Security policy and protocol threat scope

Version 0.1 treats every commerce document as untrusted input.

Implementations must defend against:

- forged sender identity;
- replay and idempotency-key reuse;
- payload alteration;
- expired commitments;
- cross-transaction reference substitution;
- confused-deputy authorization;
- duplicate and reordered delivery;
- oversized documents;
- unsafe callback endpoints; and
- disclosure of commercially sensitive payloads.

The 0.1 schemas and reference validator cover structural, decimal, identifier,
time and reference invariants. A later security profile will normatively define
credential discovery, signature canonicalization, key rotation, audience
binding and revocation. Until then, 0.1 must not be used as the sole authority
for irreversible financial execution.
