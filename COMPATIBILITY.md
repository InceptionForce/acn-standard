# Compatibility and deprecation

ACN Standard `0.1.x`, the Python SDK `0.1.x`, TypeScript SDK `0.1.x`, and ACN Cloud
`0.1.x` implement wire version `0.1`. Patch releases may clarify validation and fix
bugs but do not remove fields or document types.

Deprecations are announced in the changelog and specification, remain supported for
at least one minor release, and include a replacement and removal target. A breaking
wire change uses a new major protocol version and a distinct media-type version.

The A2A binding targets A2A `1.0`; clients must send `A2A-Version: 1.0` and the ACN
extension URI. Unknown optional envelope extensions must be preserved.
