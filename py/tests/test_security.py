from datetime import UTC, datetime
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from acn_standard import (
    ContractError,
    sign_agent_card,
    sign_envelope,
    verify_agent_card_signature,
    verify_envelope_signature,
)


class SecurityProfileTests(unittest.TestCase):
    def test_agent_card_jws_detects_tampering(self):
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        signed = sign_agent_card(
            {"name": "ACN", "version": "0.1.0", "skills": []},
            private_key,
            "card-key-1",
            jwks_url="https://acn.example/.well-known/acn-jwks.json",
        )
        header = verify_agent_card_signature(
            signed, public_key, expected_key_id="card-key-1"
        )
        self.assertEqual(header["alg"], "EdDSA")
        signed["name"] = "tampered"
        with self.assertRaises(ContractError):
            verify_agent_card_signature(signed, public_key)

    def test_sign_verify_and_detect_tampering(self):
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        value = {
            "sender": "agent:example:buyer",
            "createdAt": datetime.now(UTC).isoformat(),
            "document": {"amount": "10.00"},
        }
        signed = sign_envelope(value, private_key, "key:example:one")
        signature = verify_envelope_signature(signed, public_key)
        self.assertEqual(signature.key_id, "key:example:one")
        signed["document"]["amount"] = "11.00"
        with self.assertRaises(ContractError):
            verify_envelope_signature(signed, public_key)


if __name__ == "__main__":
    unittest.main()
