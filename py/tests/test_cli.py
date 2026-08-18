import json, tempfile, unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from acn_standard import conformance_directory
from acn_standard.cli import main

CORPUS = conformance_directory()
ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        output = StringIO()
        with redirect_stdout(output):
            code = main(list(args))
        return code, json.loads(output.getvalue())

    def test_validate_and_invalid_report(self):
        code, value = self.run_cli(
            "validate", str(CORPUS / "valid/request-for-quote.json")
        )
        self.assertEqual(code, 0)
        self.assertTrue(value["conformant"])
        code, value = self.run_cli(
            "validate", str(CORPUS / "invalid/counteroffer-wrong-total.json")
        )
        self.assertEqual(code, 1)
        self.assertEqual(value["results"][0]["error"]["code"], "acn.conformance.failed")

    def test_suite_is_machine_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "rfq.json"
            target.write_text((CORPUS / "valid/request-for-quote.json").read_text())
            code, value = self.run_cli("suite", directory)
        self.assertEqual(code, 0)
        self.assertEqual(len(value["results"]), 1)
