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

REPO = Path(__file__).resolve().parents[2]


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
npm = json.loads((REPO / "acn-sdk-typescript/package.json").read_text())
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
output = REPO / "acn-standard/dist/acn-sbom.cdx.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(sbom, indent=2) + "\n")
print(output)
