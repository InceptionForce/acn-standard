# Version negotiation and error profile

This document is normative for the ACN HTTP binding. ACN `0.1` is the only
supported commerce-contract version in this release.

An implementation publishes `GET /.well-known/acn`. The response identifies
supported versions, transports, document types, security profiles, and the
message submission endpoint. Discovery is informational; a receiver still
validates every envelope.

Clients may send `ACN-Version` on `/v1` requests. Omitting it selects `0.1` for
backward compatibility. An unsupported value returns HTTP 426 and an ACN
problem document. Every `/v1` response includes the selected `ACN-Version`
header. Selection does not modify the `specVersion` carried and signed inside
an envelope; the two values must agree when a client supplies the header.

Errors use `application/problem+json` and the schema at
`schemas/common/problem.schema.json`. `code` is stable for automation, `detail`
is safe human-readable context, and `requestId` correlates logs. Consumers must
not branch on `detail`. Servers must not include secrets or submitted payloads.
