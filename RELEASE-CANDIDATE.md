# ACN 0.1.0 release candidate

Protocol and schema development is frozen for the `0.1.0` release candidate.
Only correctness, security, documentation, and packaging fixes may enter before
the signed release tag. Any wire-breaking proposal moves to the next protocol
version and must follow `COMPATIBILITY.md`.

Release gates:

- Standard, Cloud, connector, SDK, Mongo replica-set, and live-probe tests pass.
- Specification archive manifest and SHA-256 sidecar verify.
- Python wheel and npm package build without untracked source dependencies.
- CycloneDX SBOM and dependency audit are attached.
- Agent Card signature verifies through its published JWKS.
- Mongo audit hash chain verifies after the end-to-end lifecycle.

The repository must be committed before creating the signed `acn-v0.1.0` Git tag;
the tag itself is intentionally not created from a dirty working tree.
