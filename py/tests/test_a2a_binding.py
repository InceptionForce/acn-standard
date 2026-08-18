import json
from pathlib import Path
import unittest

from acn_standard import (
    ACN_A2A_EXTENSION,
    ACN_MEDIA_TYPE,
    ACN_RESULT_MEDIA_TYPE,
    ContractError,
    a2a_result_message,
    parse_a2a_message,
)

ROOT = Path(__file__).resolve().parents[1]


def request_value():
    envelope = json.loads(
        (ROOT / "conformance/valid/request-for-quote.json").read_text()
    )
    return {
        "message": {
            "messageId": "a2a-input-001",
            "contextId": envelope["transactionId"],
            "role": "ROLE_USER",
            "parts": [{"mediaType": ACN_MEDIA_TYPE, "data": envelope}],
            "extensions": [ACN_A2A_EXTENSION],
        }
    }


class A2ABindingTests(unittest.TestCase):
    def test_parses_one_acn_data_part_and_builds_correlated_result(self):
        request = request_value()
        envelope = parse_a2a_message(request)
        self.assertEqual(envelope["messageId"], "msg_rfq000001")
        response = a2a_result_message(
            request,
            {
                "transaction_id": envelope["transactionId"],
                "message_id": envelope["messageId"],
                "status": "rfq_open",
                "duplicate": False,
            },
        )
        message = response["message"]
        self.assertEqual(message["role"], "ROLE_AGENT")
        self.assertEqual(message["metadata"]["inReplyTo"], "a2a-input-001")
        self.assertEqual(message["parts"][0]["mediaType"], ACN_RESULT_MEDIA_TYPE)

    def test_rejects_wrong_context_media_type_and_multiple_parts(self):
        for mutate in (
            lambda value: value["message"].update(contextId="txn_wrong00001"),
            lambda value: value["message"]["parts"][0].update(
                mediaType="application/json"
            ),
            lambda value: value["message"]["parts"].append(
                {"mediaType": "text/plain", "text": "x"}
            ),
        ):
            value = request_value()
            mutate(value)
            with self.subTest(value=value), self.assertRaises(ContractError):
                parse_a2a_message(value)


if __name__ == "__main__":
    unittest.main()
