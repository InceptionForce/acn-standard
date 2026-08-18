#!/usr/bin/env python3
"""Build a deterministic, checksummed ACN specification release archive."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile

# The Python project is one subtree of the repository now that the npm SDK
# shares it, so the two are distinguished: PROJECT is where the package and the
# protocol artefacts live, REPO is where the shared documents do.
PROJECT = Path(__file__).resolve().parents[1]
REPO = PROJECT.parent
ROOT = PROJECT
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from acn_standard import __version__ as VERSION  # noqa: E402

INCLUDED = (
    "specification",
    "README.md",
    "GOVERNANCE.md",
    "SECURITY.md",
    "LICENSE",
    "CHANGELOG.md",
    "COMPATIBILITY.md",
    "RELEASE-CANDIDATE.md",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"acn-standard-{VERSION}.tar.gz"
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary) / f"acn-standard-{VERSION}"
        # The corpus now ships inside the package; the archive takes it from
        # there so the two can never disagree about what conforms.
        package = PROJECT / "src" / "acn_standard"
        extras = {
            "conformance": package / "conformance",
            "schemas": package / "schemas",
        }
        for item in (*INCLUDED, *extras):
            source = extras.get(item) or PROJECT / item
            if not source.exists():
                source = REPO / item
            if not source.exists():
                raise FileNotFoundError(f"release input {item} is missing")
            if source.is_dir():
                for file in source.rglob("*"):
                    if file.is_file():
                        target = stage / item / file.relative_to(source)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(file.read_bytes())
            else:
                target = stage / item
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
        schemas = sorted(
            str(path.relative_to(stage)) for path in (stage / "schemas").rglob("*.json")
        )
        (stage / "schema-catalog.json").write_text(
            json.dumps({"specVersion": "0.1", "schemas": schemas}, indent=2) + "\n"
        )
        files = sorted(path for path in stage.rglob("*") if path.is_file())
        manifest = {
            "name": "acn-standard",
            "version": VERSION,
            "files": {str(path.relative_to(stage)): digest(path) for path in files},
        }

        (stage / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        )
        with tarfile.open(archive, "w:gz", format=tarfile.PAX_FORMAT) as bundle:
            for path in sorted([stage, *stage.rglob("*")]):
                info = bundle.gettarinfo(str(path), str(path.relative_to(stage.parent)))
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                if path.is_file():
                    with path.open("rb") as source:
                        bundle.addfile(info, source)
                else:
                    bundle.addfile(info)
    (output / f"acn-standard-{VERSION}.tar.gz.sha256").write_text(
        f"{digest(archive)}  {archive.name}\n"
    )
    return archive


if __name__ == "__main__":
    print(build(ROOT / "dist"))
