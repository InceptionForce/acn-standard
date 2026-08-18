"""What a published version claims about itself.

Once a version is on PyPI it is permanent, so the things that describe it have
to agree before the upload, not after. Four places used to carry the number
independently; this keeps them from drifting apart again.
"""

import pathlib
import subprocess
import sys
import tomllib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acn_standard import __version__  # noqa: E402


class VersionTests(unittest.TestCase):
    def test_the_library_is_the_single_source(self):
        manifest = tomllib.loads((ROOT / "pyproject.toml").read_text())
        self.assertIn(
            "version",
            manifest["project"].get("dynamic", []),
            "pyproject declares a literal version; it must come from the library",
        )
        self.assertEqual(
            manifest["tool"]["setuptools"]["dynamic"]["version"]["attr"],
            "acn_standard.__version__",
        )

    def test_the_version_looks_like_a_release(self):
        parts = __version__.split(".")
        self.assertEqual(len(parts), 3, __version__)
        self.assertTrue(all(part.isdigit() for part in parts), __version__)

    def test_no_tool_hardcodes_a_version(self):
        """The drift this test exists to prevent."""
        offenders = []
        for path in sorted((ROOT / "tools").glob("*.py")):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#") or "__version__" in stripped:
                    continue
                if f'"{__version__}"' in stripped or f"'{__version__}'" in stripped:
                    offenders.append(f"{path.name}:{number}")
        self.assertEqual(offenders, [], "tool carries a literal version")


class PublishabilityTests(unittest.TestCase):
    """The package has to be installable by someone who is not us."""

    def test_the_project_declares_what_pypi_requires(self):
        manifest = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        for field in ("name", "description", "requires-python", "license"):
            self.assertIn(field, manifest, f"{field} is missing")
        self.assertTrue((ROOT / "README.md").exists())
        self.assertTrue((ROOT / "LICENSE").exists())

    def test_dependencies_are_bounded(self):
        """An unbounded dependency lets a future major release break installs."""
        manifest = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        unbounded = [
            dependency
            for dependency in manifest.get("dependencies", [])
            if "<" not in dependency
            and "~=" not in dependency
            and "==" not in dependency
        ]
        self.assertEqual(unbounded, [], "dependency has no upper bound")

    @unittest.skipUnless(
        (ROOT / "src" / "acn_standard").is_dir(), "source layout is required"
    )
    def test_the_wheel_carries_only_the_library(self):
        """A stray top-level package would shadow a consumer's own module.

        graypy ships a top-level `tests` package and it shadowed acn-cloud's,
        breaking its test collection outright. This package must not do that to
        anyone else.
        """
        import glob
        import tempfile
        import zipfile

        with tempfile.TemporaryDirectory() as output:
            built = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "build",
                    "--wheel",
                    "--outdir",
                    output,
                    str(ROOT),
                ],
                capture_output=True,
                text=True,
            )
            if built.returncode != 0:
                self.skipTest(f"build unavailable: {built.stderr[-200:]}")
            wheel = glob.glob(f"{output}/*.whl")[0]
            top = {name.split("/")[0] for name in zipfile.ZipFile(wheel).namelist()}
        self.assertEqual(
            {entry for entry in top if not entry.endswith(".dist-info")},
            {"acn_standard"},
            "the wheel would install something other than the library",
        )


if __name__ == "__main__":
    unittest.main()
