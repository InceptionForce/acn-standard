"""The JSON Schemas and the Python validator describe one contract.

They cannot be the same artifact. Four of the invalid fixtures fail because a
declared total does not equal the sum of its line items, and JSON Schema has no
way to express that at all. So there are two layers by necessity:

    JSON Schema        shape — fields, types, patterns, enums
    validate_envelope  shape, plus cross-field arithmetic and conditionals

What can be guaranteed is that they agree where they overlap, and that where
they do not is deliberate and written down. Without this, the enum in
envelope.schema.json silently lost three document types — `credit_note`,
`return_authorization` and `return_receipt` — so every non-Python
implementation would have rejected the whole returns and credit-note lifecycle
while the Python tests stayed green.
"""

import json
import unittest

from acn_standard import (
    ContractError,
    conformance_directory,
    schema_directory,
    validate_envelope,
)

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - the extra is optional
    Draft202012Validator = None

CORPUS = conformance_directory()
SCHEMAS = schema_directory()

# Invalid fixtures the schemas do not catch, and why. Each entry is a rule a
# non-Python implementation has to enforce for itself; the test asserts this
# list is exact, so a gap cannot appear or vanish unnoticed.
SCHEMA_CANNOT_CATCH = {
    "invoice-total-mismatch": "total must equal the sum of the line items",
    "quotation-total-mismatch": "total must equal the sum of the line items",
    "counteroffer-wrong-total": "total must equal the sum of the line items",
    # Was caught by the schemas only by accident: `credit_note` was missing
    # from the documentType enum, so the envelope was rejected as an unknown
    # document rather than for its arithmetic. Fixing the enum revealed that
    # this fixture was never really covered.
    "credit-note-wrong-total": "total must equal the sum of the line items",
    # These two are expressible in JSON Schema and simply are not expressed
    # yet — exclusiveMinimum, and if/then on the rejected status.
    "goods-receipt-empty-quantities": "line quantities must be positive",
    "order-cancellation-rejected-without-reason": "a rejection requires a reason",
}


def document_schemas():
    return {
        path.stem.removesuffix(".schema").replace("-", "_"): path
        for path in SCHEMAS.rglob("*.json")
        if path.parent.name != "common"
    }


@unittest.skipIf(Draft202012Validator is None, "install jsonschema to run these")
class SchemaValidatorAgreementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.envelope = Draft202012Validator(
            json.loads((SCHEMAS / "common" / "envelope.schema.json").read_text())
        )
        cls.documents = document_schemas()

    def schema_errors(self, envelope) -> list[str]:
        """Both layers of the schema: the envelope, then its document body."""
        errors = [error.message for error in self.envelope.iter_errors(envelope)]
        path = self.documents.get(envelope.get("documentType", ""))
        if path:
            validator = Draft202012Validator(json.loads(path.read_text()))
            errors += [
                error.message
                for error in validator.iter_errors(envelope.get("document", {}))
            ]
        return errors

    def test_every_valid_envelope_satisfies_both_layers(self):
        """The check that caught the missing document types."""
        paths = sorted((CORPUS / "valid").glob("*.json"))
        self.assertGreater(len(paths), 20)
        for path in paths:
            with self.subTest(envelope=path.name):
                envelope = json.loads(path.read_text())
                validate_envelope(envelope)
                self.assertEqual(
                    self.schema_errors(envelope),
                    [],
                    f"{path.name} is valid to the library but not to the schemas",
                )

    def test_the_validator_rejects_every_invalid_envelope(self):
        for path in sorted((CORPUS / "invalid").glob("*.json")):
            with self.subTest(envelope=path.name):
                with self.assertRaises(ContractError):
                    validate_envelope(json.loads(path.read_text()))

    def test_the_gap_between_the_layers_is_exactly_what_is_documented(self):
        """Neither a new silent gap, nor a stale excuse for one that closed."""
        uncaught = set()
        for path in sorted((CORPUS / "invalid").glob("*.json")):
            envelope = json.loads(path.read_text())
            if not self.schema_errors(envelope):
                uncaught.add(path.stem)
        self.assertEqual(
            uncaught,
            set(SCHEMA_CANNOT_CATCH),
            "the schemas' coverage changed; update SCHEMA_CANNOT_CATCH and say why",
        )

    def test_every_document_type_the_corpus_uses_is_in_the_envelope_enum(self):
        enum = set(
            json.loads((SCHEMAS / "common" / "envelope.schema.json").read_text())[
                "properties"
            ]["documentType"]["enum"]
        )
        used = {
            json.loads(path.read_text())["documentType"]
            for path in (CORPUS / "valid").glob("*.json")
        }
        self.assertEqual(
            used - enum,
            set(),
            "document type the library accepts but the schema denies",
        )

    def test_every_enumerated_document_type_has_a_schema(self):
        enum = set(
            json.loads((SCHEMAS / "common" / "envelope.schema.json").read_text())[
                "properties"
            ]["documentType"]["enum"]
        )
        self.assertEqual(
            enum - set(self.documents),
            set(),
            "document type is enumerated but nothing describes its body",
        )


if __name__ == "__main__":
    unittest.main()
