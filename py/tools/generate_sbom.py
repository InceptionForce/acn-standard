#!/usr/bin/env python3
"""Generate a minimal CycloneDX SBOM from ACN package manifests."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from acn_standard import __version__ as VERSION  # noqa: E402
import re
import tomllib
import uuid

ROOT = Path(__file__).resolve().parents[1]
# The sibling projects exist when this runs inside the monorepo and do not when
# acn-standard is checked out on its own. Both are legitimate: one produces an
# SBOM for the whole network, the other for the package a consumer installs.
REPO = ROOT.parent


def component(name, version, kind="library"):
    return {
        "type": kind,
        "name": name,
        "version": version,
        "bom-ref": f"pkg:{name}@{version}",
    }


items = []
for directory in ("acn-standard", "acn-cloud", "acn-connectors/erp-reference"):
    manifest = REPO / directory / "pyproject.toml"
    if not manifest.exists():
        # Standalone checkout: the only manifest is this repository's own, which
        # sits at the root beside the language subtrees rather than inside them.
        candidates = [REPO / "pyproject.toml", ROOT / "pyproject.toml"]
        manifest = next((item for item in candidates if item.exists()), None)
        if manifest is None or directory != "acn-standard":
            continue
    value = tomllib.loads(manifest.read_text())
    project = value["project"]
    # acn-standard declares its version dynamically, so it is not in the
    # manifest; the other projects still carry a literal one.
    version = project.get("version") or (
        VERSION if project["name"] == "acn-standard" else "unspecified"
    )
    items.append(component(project["name"], version, "application"))
    dependencies = [*project.get("dependencies", [])]
    for optional in project.get("optional-dependencies", {}).values():
        dependencies.extend(optional)
    for dependency in dependencies:
        match = re.match(r"([A-Za-z0-9_.-]+)(?:\[[^]]+\])?\s*(.*)", dependency)
        items.append(component(match.group(1), match.group(2) or "unspecified"))
# The npm SDK is a sibling subtree in this repository, or a sibling
# project in the monorepo.
npm_manifest = next(
    (
        candidate
        for candidate in (
            REPO / "npm/package.json",
            REPO / "acn-sdk-typescript/package.json",
        )
        if candidate.exists()
    ),
    REPO / "npm/package.json",
)
if npm_manifest.exists():
    npm = json.loads(npm_manifest.read_text())
    items.append(component(npm["name"], npm["version"], "application"))
    for name, version in npm.get("devDependencies", {}).items():
        items.append(component(name, version))
items = sorted(
    {item["bom-ref"]: item for item in items}.values(), key=lambda item: item["bom-ref"]
)
sbom = {
    "bomFormat": "CycloneDX",
    "specVersion": "1.6",
    "serialNumber": f"urn:uuid:{uuid.uuid4()}",
    "version": 1,
    "metadata": {
        "component": component("agent-commerce-network", VERSION, "application")
    },
    "components": items,
}
output = ROOT / "dist" / "acn-sbom.cdx.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(sbom, indent=2) + "\n")
print(output)
