# Release process

1. Run `pytest` and the conformance suite.
2. Update `CHANGELOG.md`, package versions, and compatibility notes together.
3. Run `python tools/build_release.py`.
4. Verify the generated SHA-256 sidecar and inspect `manifest.json` in the archive.
5. Publish the signed tag, specification archive, Python wheel, and npm package from CI.

The release archive contains schemas, prose specifications, conformance vectors, a
schema catalog, and a checksum manifest. Generated files under `dist/` are artifacts,
not source files.
