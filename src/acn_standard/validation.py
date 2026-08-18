from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from .models import CommerceEnvelope


class ContractError(ValueError):
    """A wire document violates the normative ACN 0.1 contract."""


_MESSAGE_ID = re.compile(r"^msg_[A-Za-z0-9_-]{8,128}$")
_TRANSACTION_ID = re.compile(r"^txn_[A-Za-z0-9_-]{8,128}$")
_AGENT_ID = re.compile(r"^agent:[A-Za-z0-9._:-]{3,240}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_EXTENSION = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)+$")
_DECIMAL_2 = re.compile(r"^(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?$")
_DECIMAL_6 = re.compile(r"^(?:0|[1-9][0-9]*)(?:\.[0-9]{1,6})?$")
_ALLOWED_ENVELOPE_FIELDS = {
    "specVersion",
    "messageId",
    "transactionId",
    "documentType",
    "sender",
    "recipient",
    "createdAt",
    "expiresAt",
    "idempotencyKey",
    "inReplyTo",
    "extensions",
    "document",
    "signature",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _timestamp(value: Any, field: str) -> datetime:
    _require(isinstance(value, str), f"{field} must be an RFC 3339 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"{field} must be an RFC 3339 timestamp") from exc
    _require(parsed.tzinfo is not None, f"{field} must include a timezone")
    return parsed


def _decimal(
    value: Any, field: str, *, positive: bool = False, places: int = 6
) -> Decimal:
    _require(isinstance(value, str), f"{field} must be a decimal string")
    pattern = _DECIMAL_2 if places == 2 else _DECIMAL_6
    _require(pattern.fullmatch(value) is not None, f"{field} has invalid precision")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ContractError(f"{field} must be a decimal string") from exc
    _require(number.is_finite(), f"{field} must be finite")
    _require(number >= 0, f"{field} cannot be negative")
    if positive:
        _require(number > 0, f"{field} must be positive")
    return number


def _validate_rfq(document: dict[str, Any], created_at: datetime) -> None:
    required = {"currency", "deliveryLocation", "responseDeadline", "items"}
    _require(
        required <= document.keys(), "request_for_quote is missing required fields"
    )
    _require(not (set(document) - required), "request_for_quote has unknown fields")
    _require(_CURRENCY.fullmatch(document["currency"]) is not None, "invalid currency")
    deadline = _timestamp(document["responseDeadline"], "responseDeadline")
    _require(deadline > created_at, "responseDeadline must follow createdAt")
    items = document["items"]
    _require(
        isinstance(items, list) and 1 <= len(items) <= 500, "items must be non-empty"
    )
    line_ids: set[str] = set()
    for index, item in enumerate(items):
        _require(isinstance(item, dict), f"items[{index}] must be an object")
        allowed = {
            "lineId",
            "sku",
            "description",
            "quantity",
            "unit",
            "specifications",
        }
        _require(not (set(item) - allowed), f"items[{index}] has unknown fields")
        for field in ("lineId", "description", "quantity", "unit"):
            _require(bool(item.get(field)), f"items[{index}].{field} is required")
        _require(item["lineId"] not in line_ids, "RFQ lineId values must be unique")
        line_ids.add(item["lineId"])
        _decimal(item["quantity"], f"items[{index}].quantity", positive=True)


def _validate_quotation(document: dict[str, Any], created_at: datetime) -> None:
    required = {"currency", "validUntil", "lines", "total"}
    _require(required <= document.keys(), "quotation is missing required fields")
    allowed = required | {"paymentTerms", "deliveryTerms"}
    _require(not (set(document) - allowed), "quotation has unknown fields")
    _require(_CURRENCY.fullmatch(document["currency"]) is not None, "invalid currency")
    _require(
        _timestamp(document["validUntil"], "validUntil") > created_at,
        "quotation is expired",
    )
    lines = document["lines"]
    _require(
        isinstance(lines, list) and 1 <= len(lines) <= 500, "lines must be non-empty"
    )
    references: set[str] = set()
    calculated = Decimal("0")
    for index, line in enumerate(lines):
        _require(isinstance(line, dict), f"lines[{index}] must be an object")
        line_fields = {"rfqLineId", "quantity", "unit", "unitPrice", "lineTotal"}
        _require(not (set(line) - line_fields), f"lines[{index}] has unknown fields")
        for field in ("rfqLineId", "quantity", "unit", "unitPrice", "lineTotal"):
            _require(bool(line.get(field)), f"lines[{index}].{field} is required")
        reference = line["rfqLineId"]
        _require(
            reference not in references, "quotation RFQ line references must be unique"
        )
        references.add(reference)
        quantity = _decimal(line["quantity"], f"lines[{index}].quantity", positive=True)
        unit_price = _decimal(line["unitPrice"], f"lines[{index}].unitPrice")
        line_total = _decimal(line["lineTotal"], f"lines[{index}].lineTotal", places=2)
        _require(
            line_total == quantity * unit_price,
            f"lines[{index}].lineTotal is incorrect",
        )
        calculated += line_total
    _require(
        _decimal(document["total"], "total", places=2) == calculated,
        "quotation total is incorrect",
    )


def _validate_counteroffer(document: dict[str, Any], created_at: datetime) -> None:
    _require(
        _MESSAGE_ID.fullmatch(str(document.get("quotationMessageId", ""))) is not None,
        "invalid quotationMessageId",
    )
    terms = {
        key: value
        for key, value in document.items()
        if key not in {"quotationMessageId", "reason"}
    }
    _validate_quotation(terms, created_at)
    if "reason" in document:
        _nonempty(document["reason"], "reason", 500)


def _validate_transaction_cancellation(document: dict[str, Any]) -> None:
    _exact_fields(document, {"againstMessageId", "reason", "cancelledAt"})
    _require(
        _MESSAGE_ID.fullmatch(str(document["againstMessageId"])) is not None,
        "invalid againstMessageId",
    )
    _nonempty(document["reason"], "reason", 500)
    _timestamp(document["cancelledAt"], "cancelledAt")


def _validate_order_cancellation_request(document: dict[str, Any]) -> None:
    _exact_fields(
        document, {"purchaseOrderMessageId", "orderNumber", "reason", "requestedAt"}
    )
    _require(
        _MESSAGE_ID.fullmatch(str(document["purchaseOrderMessageId"])) is not None,
        "invalid purchaseOrderMessageId",
    )
    _nonempty(document["orderNumber"], "orderNumber", 128)
    _nonempty(document["reason"], "reason", 500)
    _timestamp(document["requestedAt"], "requestedAt")


def _validate_order_cancellation_response(document: dict[str, Any]) -> None:
    required = {"cancellationRequestMessageId", "orderNumber", "accepted", "decidedAt"}
    _exact_fields(document, required, {"rejectionReason"})
    _require(
        _MESSAGE_ID.fullmatch(str(document["cancellationRequestMessageId"]))
        is not None,
        "invalid cancellationRequestMessageId",
    )
    _nonempty(document["orderNumber"], "orderNumber", 128)
    _require(isinstance(document["accepted"], bool), "accepted must be boolean")
    _timestamp(document["decidedAt"], "decidedAt")
    if document["accepted"]:
        _require(
            "rejectionReason" not in document,
            "accepted cancellation cannot include rejectionReason",
        )
    else:
        _nonempty(document.get("rejectionReason"), "rejectionReason", 500)


def _validate_shipment_notice(document: dict[str, Any]) -> None:
    required = {
        "shipmentId",
        "purchaseOrderMessageId",
        "orderNumber",
        "shippedAt",
        "lines",
    }
    _exact_fields(document, required, {"carrier", "trackingReference"})
    _nonempty(document["shipmentId"], "shipmentId", 128)
    _require(
        _MESSAGE_ID.fullmatch(str(document["purchaseOrderMessageId"])) is not None,
        "invalid purchaseOrderMessageId",
    )
    _nonempty(document["orderNumber"], "orderNumber", 128)
    _timestamp(document["shippedAt"], "shippedAt")
    lines = document["lines"]
    _require(
        isinstance(lines, list) and 1 <= len(lines) <= 500,
        "shipment lines must be non-empty",
    )
    references = set()
    for index, line in enumerate(lines):
        _require(isinstance(line, dict), f"lines[{index}] must be an object")
        _exact_fields(line, {"rfqLineId", "quantity", "unit"})
        reference = line["rfqLineId"]
        _nonempty(reference, f"lines[{index}].rfqLineId", 128)
        _require(reference not in references, "shipment line references must be unique")
        references.add(reference)
        _decimal(line["quantity"], f"lines[{index}].quantity", positive=True)
        _nonempty(line["unit"], f"lines[{index}].unit", 32)


def _validate_goods_receipt(document: dict[str, Any]) -> None:
    required = {
        "receiptId",
        "shipmentNoticeMessageId",
        "orderNumber",
        "receivedAt",
        "lines",
    }
    _exact_fields(document, required, {"note"})
    _nonempty(document["receiptId"], "receiptId", 128)
    _require(
        _MESSAGE_ID.fullmatch(str(document["shipmentNoticeMessageId"])) is not None,
        "invalid shipmentNoticeMessageId",
    )
    _nonempty(document["orderNumber"], "orderNumber", 128)
    _timestamp(document["receivedAt"], "receivedAt")
    lines = document["lines"]
    _require(
        isinstance(lines, list) and 1 <= len(lines) <= 500,
        "receipt lines must be non-empty",
    )
    references = set()
    for index, line in enumerate(lines):
        _require(isinstance(line, dict), f"lines[{index}] must be an object")
        _exact_fields(
            line,
            {"rfqLineId", "acceptedQuantity", "rejectedQuantity", "unit"},
            {"rejectionReason"},
        )
        reference = line["rfqLineId"]
        _nonempty(reference, f"lines[{index}].rfqLineId", 128)
        _require(reference not in references, "receipt line references must be unique")
        references.add(reference)
        accepted = _decimal(
            line["acceptedQuantity"], f"lines[{index}].acceptedQuantity"
        )
        rejected = _decimal(
            line["rejectedQuantity"], f"lines[{index}].rejectedQuantity"
        )
        _require(accepted + rejected > 0, "receipt line quantity must be positive")
        _nonempty(line["unit"], f"lines[{index}].unit", 32)
        if rejected > 0:
            _nonempty(
                line.get("rejectionReason"), f"lines[{index}].rejectionReason", 500
            )
        else:
            _require(
                "rejectionReason" not in line,
                "accepted receipt line cannot include rejectionReason",
            )


def _exact_fields(
    document: dict[str, Any], required: set[str], optional: set[str] | None = None
) -> None:
    _require(required <= document.keys(), "document is missing required fields")
    _require(
        not (set(document) - required - (optional or set())),
        "document has unknown fields",
    )


def _nonempty(value: Any, field: str, maximum: int = 255) -> None:
    _require(isinstance(value, str) and 1 <= len(value) <= maximum, f"invalid {field}")


def _validate_acceptance(document: dict[str, Any]) -> None:
    _exact_fields(document, {"quotationMessageId"})
    _require(
        _MESSAGE_ID.fullmatch(str(document["quotationMessageId"])) is not None,
        "invalid quotationMessageId",
    )


def _validate_order(document: dict[str, Any]) -> None:
    required = {
        "orderNumber",
        "quotationMessageId",
        "currency",
        "deliveryLocation",
        "lines",
        "total",
    }
    _exact_fields(document, required)
    _nonempty(document["orderNumber"], "orderNumber", 128)
    _require(
        _MESSAGE_ID.fullmatch(str(document["quotationMessageId"])) is not None,
        "invalid quotationMessageId",
    )
    _require(
        _CURRENCY.fullmatch(str(document["currency"])) is not None, "invalid currency"
    )
    _nonempty(document["deliveryLocation"], "deliveryLocation", 500)
    lines = document["lines"]
    _require(
        isinstance(lines, list) and 1 <= len(lines) <= 500, "lines must be non-empty"
    )
    calculated = Decimal("0")
    references = set()
    for index, line in enumerate(lines):
        _require(isinstance(line, dict), f"lines[{index}] must be an object")
        fields = {"rfqLineId", "quantity", "unit", "unitPrice", "lineTotal"}
        _exact_fields(line, fields)
        reference = line["rfqLineId"]
        _nonempty(reference, f"lines[{index}].rfqLineId", 128)
        _require(
            reference not in references, "purchase order line references must be unique"
        )
        references.add(reference)
        quantity = _decimal(line["quantity"], f"lines[{index}].quantity", positive=True)
        price = _decimal(line["unitPrice"], f"lines[{index}].unitPrice")
        total = _decimal(line["lineTotal"], f"lines[{index}].lineTotal", places=2)
        _nonempty(line["unit"], f"lines[{index}].unit", 32)
        _require(total == quantity * price, f"lines[{index}].lineTotal is incorrect")
        calculated += total
    _require(
        _decimal(document["total"], "total", places=2) == calculated,
        "purchase order total is incorrect",
    )


def _validate_order_acknowledgement(
    document: dict[str, Any], created_at: datetime
) -> None:
    required = {"purchaseOrderMessageId", "orderNumber", "accepted"}
    optional = {"expectedDeliveryAt", "rejectionReason"}
    _exact_fields(document, required, optional)
    _require(
        _MESSAGE_ID.fullmatch(str(document["purchaseOrderMessageId"])) is not None,
        "invalid purchaseOrderMessageId",
    )
    _nonempty(document["orderNumber"], "orderNumber", 128)
    _require(isinstance(document["accepted"], bool), "accepted must be boolean")
    if document["accepted"]:
        _require(
            "rejectionReason" not in document,
            "accepted order cannot include rejectionReason",
        )
        if "expectedDeliveryAt" in document:
            _require(
                _timestamp(document["expectedDeliveryAt"], "expectedDeliveryAt")
                > created_at,
                "expectedDeliveryAt must follow createdAt",
            )
    else:
        _nonempty(document.get("rejectionReason"), "rejectionReason", 500)


def _validate_fulfillment(document: dict[str, Any]) -> None:
    required = {"purchaseOrderMessageId", "orderNumber", "status", "occurredAt"}
    _exact_fields(document, required, {"trackingReference", "note"})
    _require(
        _MESSAGE_ID.fullmatch(str(document["purchaseOrderMessageId"])) is not None,
        "invalid purchaseOrderMessageId",
    )
    _nonempty(document["orderNumber"], "orderNumber", 128)
    _require(
        document["status"] in {"processing", "shipped", "delivered"},
        "invalid fulfillment status",
    )
    _timestamp(document["occurredAt"], "occurredAt")
    for field in ("trackingReference", "note"):
        if field in document:
            _nonempty(document[field], field, 500)


def _validate_invoice(document: dict[str, Any], created_at: datetime) -> None:
    required = {
        "invoiceNumber",
        "purchaseOrderMessageId",
        "currency",
        "subtotal",
        "tax",
        "total",
        "dueAt",
    }
    _exact_fields(document, required)
    _nonempty(document["invoiceNumber"], "invoiceNumber", 128)
    _require(
        _MESSAGE_ID.fullmatch(str(document["purchaseOrderMessageId"])) is not None,
        "invalid purchaseOrderMessageId",
    )
    _require(
        _CURRENCY.fullmatch(str(document["currency"])) is not None, "invalid currency"
    )
    subtotal = _decimal(document["subtotal"], "subtotal", places=2)
    tax = _decimal(document["tax"], "tax", places=2)
    total = _decimal(document["total"], "total", places=2)
    _require(total == subtotal + tax, "invoice total is incorrect")
    _require(
        _timestamp(document["dueAt"], "dueAt") > created_at,
        "invoice dueAt must follow createdAt",
    )


def _validate_payment_intent(document: dict[str, Any]) -> None:
    required = {"invoiceMessageId", "currency", "amount", "intentReference"}
    _exact_fields(document, required, {"paymentMethod", "provider"})
    _require(
        _MESSAGE_ID.fullmatch(str(document["invoiceMessageId"])) is not None,
        "invalid invoiceMessageId",
    )
    _require(
        _CURRENCY.fullmatch(str(document["currency"])) is not None, "invalid currency"
    )
    _decimal(document["amount"], "amount", positive=True, places=2)
    _nonempty(document["intentReference"], "intentReference", 128)
    for field in ("paymentMethod", "provider"):
        if field in document:
            _nonempty(document[field], field, 128)


def _validate_approval_evidence(document: dict[str, Any]) -> None:
    required = {
        "acceptanceMessageId",
        "evidenceId",
        "policyId",
        "decision",
        "decidedAt",
        "approver",
    }
    _exact_fields(document, required, {"reason"})
    _require(
        _MESSAGE_ID.fullmatch(str(document["acceptanceMessageId"])) is not None,
        "invalid acceptanceMessageId",
    )
    _nonempty(document["evidenceId"], "evidenceId", 128)
    _nonempty(document["policyId"], "policyId", 128)
    _require(
        document["decision"] in {"approved", "rejected"}, "invalid approval decision"
    )
    _timestamp(document["decidedAt"], "decidedAt")
    _require(
        _AGENT_ID.fullmatch(str(document["approver"])) is not None, "invalid approver"
    )
    if document["decision"] == "rejected":
        _nonempty(document.get("reason"), "reason", 500)


def _validate_payment_result(document: dict[str, Any]) -> None:
    required = {
        "paymentIntentMessageId",
        "resultReference",
        "status",
        "currency",
        "amount",
        "occurredAt",
        "provider",
    }
    _exact_fields(document, required, {"failureReason"})
    _require(
        _MESSAGE_ID.fullmatch(str(document["paymentIntentMessageId"])) is not None,
        "invalid paymentIntentMessageId",
    )
    _nonempty(document["resultReference"], "resultReference", 128)
    _require(
        document["status"] in {"authorized", "captured", "failed"},
        "invalid payment result status",
    )
    _require(
        _CURRENCY.fullmatch(str(document["currency"])) is not None, "invalid currency"
    )
    _decimal(document["amount"], "amount", positive=True, places=2)
    _timestamp(document["occurredAt"], "occurredAt")
    _nonempty(document["provider"], "provider", 128)
    if document["status"] == "failed":
        _nonempty(document.get("failureReason"), "failureReason", 500)


def _validate_settlement(document: dict[str, Any]) -> None:
    required = {
        "paymentResultMessageId",
        "settlementReference",
        "status",
        "currency",
        "amount",
        "occurredAt",
    }
    _exact_fields(document, required, {"reason"})
    _require(
        _MESSAGE_ID.fullmatch(str(document["paymentResultMessageId"])) is not None,
        "invalid paymentResultMessageId",
    )
    _nonempty(document["settlementReference"], "settlementReference", 128)
    _require(document["status"] in {"settled", "reversed"}, "invalid settlement status")
    _require(
        _CURRENCY.fullmatch(str(document["currency"])) is not None, "invalid currency"
    )
    _decimal(document["amount"], "amount", positive=True, places=2)
    _timestamp(document["occurredAt"], "occurredAt")
    if document["status"] == "reversed":
        _nonempty(document.get("reason"), "reason", 500)


def _validate_dispute_opened(document: dict[str, Any]) -> None:
    required = {"disputeId", "againstMessageId", "category", "description"}
    _exact_fields(document, required, {"currency", "amount"})
    _nonempty(document["disputeId"], "disputeId", 128)
    _require(
        _MESSAGE_ID.fullmatch(str(document["againstMessageId"])) is not None,
        "invalid againstMessageId",
    )
    _require(
        document["category"]
        in {"quantity", "quality", "delivery", "invoice", "payment", "other"},
        "invalid dispute category",
    )
    _nonempty(document["description"], "description", 1000)
    if "amount" in document or "currency" in document:
        _require(
            {"amount", "currency"} <= document.keys(),
            "disputed amount requires currency",
        )
        _require(
            _CURRENCY.fullmatch(str(document["currency"])) is not None,
            "invalid currency",
        )
        _decimal(document["amount"], "amount", positive=True, places=2)


def _validate_dispute_resolved(document: dict[str, Any]) -> None:
    required = {"disputeId", "disputeMessageId", "resolution", "resolvedAt"}
    _exact_fields(document, required, {"note", "agreedAmount", "currency"})
    _nonempty(document["disputeId"], "disputeId", 128)
    _require(
        _MESSAGE_ID.fullmatch(str(document["disputeMessageId"])) is not None,
        "invalid disputeMessageId",
    )
    _require(
        document["resolution"] in {"accepted", "rejected", "partial", "withdrawn"},
        "invalid dispute resolution",
    )
    _timestamp(document["resolvedAt"], "resolvedAt")
    if "agreedAmount" in document or "currency" in document:
        _require(
            {"agreedAmount", "currency"} <= document.keys(),
            "agreed amount requires currency",
        )
        _require(
            _CURRENCY.fullmatch(str(document["currency"])) is not None,
            "invalid currency",
        )
        _decimal(document["agreedAmount"], "agreedAmount", places=2)


def _validate_return_lines(lines: Any) -> None:
    _require(
        isinstance(lines, list) and 1 <= len(lines) <= 500,
        "return lines must be non-empty",
    )
    references = set()
    for index, line in enumerate(lines):
        _require(isinstance(line, dict), f"lines[{index}] must be an object")
        _exact_fields(line, {"rfqLineId", "quantity", "unit"}, {"reason"})
        reference = line["rfqLineId"]
        _nonempty(reference, f"lines[{index}].rfqLineId", 128)
        _require(reference not in references, "return line references must be unique")
        references.add(reference)
        _decimal(line["quantity"], f"lines[{index}].quantity", positive=True)
        _nonempty(line["unit"], f"lines[{index}].unit", 32)
        if "reason" in line:
            _nonempty(line["reason"], f"lines[{index}].reason", 500)


def _validate_return_authorization(
    document: dict[str, Any], created_at: datetime
) -> None:
    _exact_fields(
        document,
        {"authorizationId", "disputeMessageId", "orderNumber", "expiresAt", "lines"},
        {"instructions"},
    )
    _nonempty(document["authorizationId"], "authorizationId", 128)
    _require(
        _MESSAGE_ID.fullmatch(str(document["disputeMessageId"])) is not None,
        "invalid disputeMessageId",
    )
    _nonempty(document["orderNumber"], "orderNumber", 128)
    _require(
        _timestamp(document["expiresAt"], "expiresAt") > created_at,
        "return authorization is expired",
    )
    _validate_return_lines(document["lines"])
    if "instructions" in document:
        _nonempty(document["instructions"], "instructions", 1000)


def _validate_return_receipt(document: dict[str, Any]) -> None:
    _exact_fields(
        document,
        {"receiptId", "authorizationMessageId", "receivedAt", "lines"},
        {"note"},
    )
    _nonempty(document["receiptId"], "receiptId", 128)
    _require(
        _MESSAGE_ID.fullmatch(str(document["authorizationMessageId"])) is not None,
        "invalid authorizationMessageId",
    )
    _timestamp(document["receivedAt"], "receivedAt")
    _validate_return_lines(document["lines"])
    if "note" in document:
        _nonempty(document["note"], "note", 500)


def _validate_credit_note(document: dict[str, Any]) -> None:
    _exact_fields(
        document,
        {
            "creditNoteNumber",
            "invoiceMessageId",
            "returnReceiptMessageId",
            "currency",
            "subtotal",
            "tax",
            "total",
            "issuedAt",
        },
        {"reason"},
    )
    _nonempty(document["creditNoteNumber"], "creditNoteNumber", 128)
    for field in ("invoiceMessageId", "returnReceiptMessageId"):
        _require(
            _MESSAGE_ID.fullmatch(str(document[field])) is not None,
            f"invalid {field}",
        )
    _require(
        _CURRENCY.fullmatch(str(document["currency"])) is not None, "invalid currency"
    )
    subtotal = _decimal(document["subtotal"], "subtotal", positive=True, places=2)
    tax = _decimal(document["tax"], "tax", places=2)
    total = _decimal(document["total"], "total", positive=True, places=2)
    _require(total == subtotal + tax, "credit note total is incorrect")
    _timestamp(document["issuedAt"], "issuedAt")
    if "reason" in document:
        _nonempty(document["reason"], "reason", 500)


def validate_envelope(value: dict[str, Any]) -> CommerceEnvelope:
    _require(isinstance(value, dict), "envelope must be an object")
    _require(not (set(value) - _ALLOWED_ENVELOPE_FIELDS), "envelope has unknown fields")
    _require(value.get("specVersion") == "0.1", "unsupported specVersion")
    _require(
        _MESSAGE_ID.fullmatch(str(value.get("messageId", ""))) is not None,
        "invalid messageId",
    )
    _require(
        _TRANSACTION_ID.fullmatch(str(value.get("transactionId", ""))) is not None,
        "invalid transactionId",
    )
    _require(
        _AGENT_ID.fullmatch(str(value.get("sender", ""))) is not None, "invalid sender"
    )
    _require(
        _AGENT_ID.fullmatch(str(value.get("recipient", ""))) is not None,
        "invalid recipient",
    )
    _require(value["sender"] != value["recipient"], "sender and recipient must differ")
    _require(
        isinstance(value.get("idempotencyKey"), str)
        and 1 <= len(value["idempotencyKey"]) <= 255,
        "invalid idempotencyKey",
    )
    created_at = _timestamp(value.get("createdAt"), "createdAt")
    expires_at = _timestamp(value.get("expiresAt"), "expiresAt")
    _require(expires_at > created_at, "expiresAt must follow createdAt")
    document = value.get("document")
    _require(isinstance(document, dict), "document must be an object")
    extensions = value.get("extensions", {})
    _require(isinstance(extensions, dict), "extensions must be an object")
    _require(
        all(_EXTENSION.fullmatch(key) for key in extensions),
        "extensions must use namespaced keys",
    )
    document_type = value.get("documentType")
    from .extensions import validate_network_extension

    validate_network_extension(extensions, str(document_type))
    reply_documents = {
        "quotation",
        "quotation_counteroffer",
        "transaction_cancellation",
        "order_cancellation_request",
        "order_cancellation_response",
        "shipment_notice",
        "goods_receipt",
        "quotation_acceptance",
        "purchase_order",
        "order_acknowledgement",
        "fulfillment_status",
        "invoice",
        "payment_intent",
        "approval_evidence",
        "payment_result",
        "settlement_confirmation",
        "dispute_opened",
        "dispute_resolved",
        "return_authorization",
        "return_receipt",
        "credit_note",
    }
    if document_type in reply_documents:
        _require(
            _MESSAGE_ID.fullmatch(str(value.get("inReplyTo", ""))) is not None,
            f"{document_type} requires inReplyTo",
        )
    if document_type == "request_for_quote":
        _require(
            value.get("inReplyTo") is None, "request_for_quote cannot use inReplyTo"
        )
        _validate_rfq(document, created_at)
    elif document_type == "quotation":
        _require(
            _MESSAGE_ID.fullmatch(str(value.get("inReplyTo", ""))) is not None,
            "quotation requires inReplyTo",
        )
        _validate_quotation(document, created_at)
    elif document_type == "quotation_counteroffer":
        _validate_counteroffer(document, created_at)
    elif document_type == "transaction_cancellation":
        _validate_transaction_cancellation(document)
    elif document_type == "order_cancellation_request":
        _validate_order_cancellation_request(document)
    elif document_type == "order_cancellation_response":
        _validate_order_cancellation_response(document)
    elif document_type == "shipment_notice":
        _validate_shipment_notice(document)
    elif document_type == "goods_receipt":
        _validate_goods_receipt(document)
    elif document_type == "quotation_acceptance":
        _validate_acceptance(document)
    elif document_type == "purchase_order":
        _validate_order(document)
    elif document_type == "order_acknowledgement":
        _validate_order_acknowledgement(document, created_at)
    elif document_type == "fulfillment_status":
        _validate_fulfillment(document)
    elif document_type == "invoice":
        _validate_invoice(document, created_at)
    elif document_type == "payment_intent":
        _validate_payment_intent(document)
    elif document_type == "approval_evidence":
        _validate_approval_evidence(document)
    elif document_type == "payment_result":
        _validate_payment_result(document)
    elif document_type == "settlement_confirmation":
        _validate_settlement(document)
    elif document_type == "dispute_opened":
        _validate_dispute_opened(document)
    elif document_type == "dispute_resolved":
        _validate_dispute_resolved(document)
    elif document_type == "return_authorization":
        _validate_return_authorization(document, created_at)
    elif document_type == "return_receipt":
        _validate_return_receipt(document)
    elif document_type == "credit_note":
        _validate_credit_note(document)
    else:
        raise ContractError("unsupported documentType")
    return CommerceEnvelope(
        spec_version="0.1",
        message_id=value["messageId"],
        transaction_id=value["transactionId"],
        document_type=document_type,
        sender=value["sender"],
        recipient=value["recipient"],
        created_at=created_at,
        expires_at=expires_at,
        idempotency_key=value["idempotencyKey"],
        in_reply_to=value.get("inReplyTo"),
        extensions=extensions,
        document=document,
    )
