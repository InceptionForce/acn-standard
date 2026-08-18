import io
import json
import unittest
from datetime import UTC, datetime
from unittest.mock import patch
from urllib.error import HTTPError

from acn_standard import AcnClient, AcnClientError, build_envelope, validate_envelope


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


class SdkTests(unittest.TestCase):
    def test_build_envelope_uses_wire_names_and_supplied_time(self):
        value = build_envelope(
            document_type="request-for-quote",
            sender="agent:buyer",
            recipient="agent:seller",
            document={"currency": "USD"},
            now=datetime(2026, 1, 1, tzinfo=UTC),
        )
        self.assertEqual(value["specVersion"], "0.1")
        self.assertEqual(value["createdAt"], "2026-01-01T00:00:00Z")
        self.assertTrue(value["messageId"].startswith("msg_"))

    def test_generated_envelope_satisfies_the_contract(self):
        envelope = build_envelope(
            document_type="request_for_quote",
            sender="agent:company-a:procurement",
            recipient="agent:company-b:sales",
            document={
                "currency": "GHS",
                "deliveryLocation": "Accra",
                "responseDeadline": "2026-01-02T00:00:00Z",
                "items": [
                    {
                        "lineId": "line-1",
                        "description": "A4 paper",
                        "quantity": "10",
                        "unit": "box",
                    }
                ],
            },
            now=datetime(2026, 1, 1, tzinfo=UTC),
        )
        self.assertEqual(validate_envelope(envelope).document_type, "request_for_quote")

    def test_submit_maps_response(self):
        captured = {}

        def open_request(request, timeout):
            captured["request"] = request
            return Response(
                json.dumps(
                    {
                        "transaction_id": "txn:1",
                        "message_id": "msg:1",
                        "status": "open",
                        "duplicate": False,
                    }
                ).encode()
            )

        with patch("acn_standard.sdk.urlopen", open_request):
            result = AcnClient("https://acn.example", retry_attempts=0).submit(
                {"hello": "world"}
            )
        self.assertEqual(result.transaction_id, "txn:1")
        self.assertEqual(captured["request"].headers["Acn-version"], "0.1")

    def test_transient_failure_is_retried(self):
        attempts = []

        def open_request(request, timeout):
            attempts.append(request)
            if len(attempts) == 1:
                raise HTTPError(request.full_url, 503, "down", {}, io.BytesIO(b"{}"))
            return Response(
                json.dumps(
                    {
                        "transaction_id": "txn:1",
                        "message_id": "msg:1",
                        "status": "open",
                        "duplicate": False,
                    }
                ).encode()
            )

        with patch("acn_standard.sdk.urlopen", open_request):
            AcnClient("https://acn.example", sleeper=lambda _: None).submit({})
        self.assertEqual(len(attempts), 2)

    def test_non_https_remote_url_is_rejected(self):
        with self.assertRaises(ValueError):
            AcnClient("http://acn.example")

    def test_typed_non_retryable_error(self):
        def open_request(request, timeout):
            body = io.BytesIO(b'{"code":"acn.document.invalid","detail":"bad"}')
            raise HTTPError(request.full_url, 422, "bad", {}, body)

        with patch("acn_standard.sdk.urlopen", open_request):
            with self.assertRaises(AcnClientError) as caught:
                AcnClient("https://acn.example").submit({})
        self.assertEqual(caught.exception.code, "acn.document.invalid")
        self.assertFalse(caught.exception.retryable)


class DeliveryLeaseTests(unittest.TestCase):
    """A claimed delivery is completed against its lease, or not at all."""

    def _capture(self):
        captured = {}

        def open_request(request, timeout):
            captured["body"] = json.loads(request.data)
            captured["url"] = request.full_url
            return Response(b"{}")

        return captured, open_request

    def test_acknowledge_sends_the_lease_the_claim_returned(self):
        captured, open_request = self._capture()
        with patch("acn_standard.sdk.urlopen", open_request):
            AcnClient("https://acn.example").acknowledge_delivery(
                "delivery-1", {"agentId": "agent:a"}, lease_id="lease-9"
            )
        # Without leaseId the server cannot match the lease and answers 409.
        self.assertEqual(captured["body"]["leaseId"], "lease-9")
        self.assertTrue(captured["url"].endswith("/v1/delivery/delivery-1/ack"))

    def test_reject_sends_the_lease_and_reason(self):
        captured, open_request = self._capture()
        with patch("acn_standard.sdk.urlopen", open_request):
            AcnClient("https://acn.example").reject_delivery(
                "delivery-1",
                {"agentId": "agent:a"},
                reason="no trigger",
                lease_id="lease-9",
            )
        self.assertEqual(captured["body"]["leaseId"], "lease-9")
        self.assertEqual(captured["body"]["reason"], "no trigger")


if __name__ == "__main__":
    unittest.main()
