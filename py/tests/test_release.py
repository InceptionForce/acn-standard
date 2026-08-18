import hashlib
import importlib.util
import tarfile
import tempfile
import unittest

from acn_standard import __version__
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools/build_release.py"
SPEC = importlib.util.spec_from_file_location("acn_build_release", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ReleaseTests(unittest.TestCase):
    def test_release_contains_catalog_and_matching_checksum(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            archive = MODULE.build(output)
            expected = (output / f"{archive.name}.sha256").read_text().split()[0]
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), expected)
            with tarfile.open(archive) as bundle:
                names = bundle.getnames()
            self.assertIn(f"acn-standard-{__version__}/manifest.json", names)
            self.assertIn(f"acn-standard-{__version__}/schema-catalog.json", names)


if __name__ == "__main__":
    unittest.main()
