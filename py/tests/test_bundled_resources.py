"""The data that ships with the library.

Both the conformance corpus and the JSON Schemas travel inside the package now.
That is worth testing for a reason beyond "the files are present": the library
validates envelopes in hand-written Python, and the schemas state the same
contract for everyone else. Two descriptions of one contract drift unless
something compares them, and until now nothing did.
"""

import json
import unittest

from acn_standard import (
    conformance_directory,
    schema_directory,
    validate_envelope,
    ContractError,
)

CORPUS = conformance_directory()
SCHEMAS = schema_directory()


class BundledCorpusTests(unittest.TestCase):
    def test_the_corpus_ships_with_the_package(self):
        self.assertTrue((CORPUS / "valid").is_dir(), CORPUS)
        self.assertTrue((CORPUS / "invalid").is_dir(), CORPUS)

    def test_every_valid_envelope_validates(self):
        paths = sorted((CORPUS / "valid").glob("*.json"))
        self.assertGreater(len(paths), 20, "the bundled corpus looks truncated")
        for path in paths:
            with self.subTest(envelope=path.name):
                validate_envelope(json.loads(path.read_text()))

    def test_every_invalid_envelope_is_rejected(self):
        paths = sorted((CORPUS / "invalid").glob("*.json"))
        self.assertGreater(len(paths), 0)
        for path in paths:
            with self.subTest(envelope=path.name):
                with self.assertRaises(ContractError):
                    validate_envelope(json.loads(path.read_text()))


class BundledSchemaTests(unittest.TestCase):
    def test_the_schemas_ship_with_the_package(self):
        schemas = sorted(SCHEMAS.rglob("*.json"))
        self.assertGreater(len(schemas), 20, f"only {len(schemas)} schemas bundled")

    def test_every_schema_is_readable_json_with_an_identifier(self):
        for path in sorted(SCHEMAS.rglob("*.json")):
            with self.subTest(schema=path.name):
                value = json.loads(path.read_text())
                self.assertIsInstance(value, dict)
                self.assertTrue(
                    value.get("$id") or value.get("title"),
                    f"{path.name} identifies nothing",
                )

    def test_every_document_type_in_the_corpus_has_a_schema(self):
        """The drift this pairing exists to catch.

        A document type added to the corpus but not to the schemas leaves every
        non-Python implementation unable to validate it, and the Python tests
        would still pass.
        """
        described = {
            path.stem.removesuffix(".schema") for path in SCHEMAS.rglob("*.json")
        }
        missing = set()
        for path in sorted((CORPUS / "valid").glob("*.json")):
            document_type = json.loads(path.read_text())["documentType"]
            # Schemas are named for the document, corpus files for the example;
            # several examples share a document type.
            if document_type.replace("_", "-") not in described:
                missing.add(document_type)
        self.assertEqual(missing, set(), "document type has no schema")


if __name__ == "__main__":
    unittest.main()
