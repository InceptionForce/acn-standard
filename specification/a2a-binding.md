# ACN binding for A2A 1.0

ACN uses the A2A Message/Part model as a transport binding. Commerce semantics
remain entirely defined by the signed ACN envelope.

The server publishes `/.well-known/agent-card.json` and an `HTTP+JSON` A2A 1.0
interface. A client calls `POST /a2a/v1/message:send` with `A2A-Version: 1.0`
and advertises the ACN extension URI in `A2A-Extensions`.
The request and response content type is `application/a2a+json`; message roles
use the A2A 1.0 enum names `ROLE_USER` and `ROLE_AGENT`.

The user Message contains exactly one structured-data Part with media type
`application/vnd.acn+json`; its `data` is a complete ACN envelope. When present,
the A2A `contextId` MUST equal the ACN `transactionId`. Cloud validates the A2A
shape, then applies the same signature, contract, governance, idempotency, and
transaction service used by direct HTTP.

Acceptance is synchronous, so the response is an agent Message rather than an
artificial long-running Task. Its single structured-data Part uses
`application/vnd.acn.result+json` and contains transaction ID, message ID,
commercial status, and duplicate flag. The response metadata identifies the
input A2A message. A2A Messages are transport wrappers and MUST NOT be treated
as commercial evidence; the immutable ACN envelope is the evidence.

The legacy `/v1/a2a/tasks` endpoint remains a compatibility adapter for the
earlier ACN draft and is not the normative A2A 1.0 binding.

A2A route failures use the HTTP+JSON `google.rpc.Status` representation with a
`google.rpc.ErrorInfo` detail in domain `a2a-protocol.org`. Unsupported version,
missing required extension, and unsupported Part media type use reasons
`VERSION_NOT_SUPPORTED`, `EXTENSION_SUPPORT_REQUIRED`, and
`CONTENT_TYPE_NOT_SUPPORTED`. ACN `/v1` routes continue to use ACN problem
documents.
