import json
from pathlib import Path
import unittest

from acn_standard import ContractError, validate_envelope

ROOT = Path(__file__).resolve().parents[1]


class ConformanceTests(unittest.TestCase):
    def test_valid_fixtures(self):
        for path in sorted((ROOT / "conformance" / "valid").glob("*.json")):
            with self.subTest(path=path.name):
                value = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(validate_envelope(value).to_wire(), value)

    def test_invalid_fixtures(self):
        for path in sorted((ROOT / "conformance" / "invalid").glob("*.json")):
            with self.subTest(path=path.name):
                value = json.loads(path.read_text(encoding="utf-8"))
                with self.assertRaises(ContractError):
                    validate_envelope(value)

    def test_network_extension_categories_and_reservation_evidence(self):
        value = json.loads((ROOT / "conformance/valid/purchase-order.json").read_text())
        value["extensions"] = {
            "acn.network": {
                "productCategories": ["office-supplies/paper"],
                "reservationEvidence": {
                    "reservationId": "reservation:quote-1",
                    "quotationMessageId": value["document"]["quotationMessageId"],
                    "provider": "inventory.example",
                    "expiresAt": "2026-08-16T10:00:00Z",
                    "evidenceHash": "sha256:" + "a" * 64,
                },
            }
        }
        self.assertEqual(validate_envelope(value).extensions, value["extensions"])
        value["extensions"]["acn.network"]["reservationEvidence"][
            "evidenceHash"
        ] = "sha256:weak"
        with self.assertRaises(ContractError):
            validate_envelope(value)

    def test_reservation_evidence_is_rejected_outside_purchase_order(self):
        value = json.loads(
            (ROOT / "conformance/valid/request-for-quote.json").read_text()
        )
        value["extensions"] = {
            "acn.network": {
                "reservationEvidence": {
                    "reservationId": "reservation:quote-1",
                    "quotationMessageId": "msg_quote00001",
                    "provider": "inventory.example",
                    "expiresAt": "2026-08-16T10:00:00Z",
                    "evidenceHash": "sha256:" + "a" * 64,
                }
            }
        }
        with self.assertRaises(ContractError):
            validate_envelope(value)


if __name__ == "__main__":
    unittest.main()
