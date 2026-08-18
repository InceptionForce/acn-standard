# Procurement lifecycle 0.1

## Request for quote

A buyer creates a `request_for_quote`. It MUST contain at least one item, a
currency and a response deadline. The deadline MUST be later than creation.

An RFQ begins in `open` state and may become `quoted`, `withdrawn` or `expired`.

## Quotation

A seller creates a `quotation` referencing an open RFQ. The quotation:

- MUST retain the RFQ transaction identifier;
- MUST identify the RFQ with `inReplyTo`;
- MUST use the RFQ currency;
- MUST contain a positive quantity for every quoted line;
- MUST encode quantities and money as JSON strings containing base-10 decimals;
- MUST expire later than its creation time; and
- MUST NOT quote more than one line for the same RFQ line identifier.

Creating the first valid quotation moves the transaction from `rfq_open` to
`quoted`. Additional quotations MAY be accepted while the RFQ remains open.

## Quotation acceptance and purchase order

The buyer accepts exactly one known quotation. The acceptance MUST reference
that quotation in both `inReplyTo` and `quotationMessageId`. A purchase order
requires `approval_evidence` referencing the acceptance. Evidence records the
policy, approver, decision, and decision time. Rejection is terminal. An
approved purchase order references the evidence, retains the accepted
quotation and currency, and cannot exceed RFQ quantities. Totals MUST be exact.

## Order acknowledgement and fulfillment

The supplier accepts or rejects the purchase order, retaining its order number
and reference. Rejection is terminal in 0.1. After acceptance, fulfillment may
advance through `processing`, `shipped`, and `delivered`, but cannot move
backwards. Each update references the prior lifecycle message and order.

For line-level fulfillment, a supplier sends one or more `shipment_notice`
documents. Cumulative shipped quantity cannot exceed ordered quantity plus
previously rejected quantity. The buyer answers each shipment exactly once
with `goods_receipt`; every shipped line and quantity must be accounted for as
accepted or rejected. Cumulative accepted quantity cannot exceed the order.
The transaction is `partially_received` until accepted quantities equal every
purchase-order line, at which point it is fulfilled and may be invoiced.

## Cancellation

Before a purchase order exists, the buyer may end an active transaction with
`transaction_cancellation`, referencing the latest lifecycle message. This is
a terminal commercial fact; it does not erase prior signed messages.

After ordering, either party may send `order_cancellation_request` while the
order is ordered, acknowledged, or only processing. The counterparty answers
with `order_cancellation_response`. Acceptance makes the order terminally
cancelled; rejection restores the exact prior lifecycle state. A shipped,
delivered, invoiced, paid, or settled order instead requires a return, credit,
reversal, or dispute flow.

## Invoice and payment intent boundary

The supplier may invoice only after delivery. The invoice retains order
currency and satisfies `total = subtotal + tax`. ACN Cloud 0.1 also requires
the total to equal the order total.

The buyer may create a payment intent for the exact invoice amount. It records
an orchestration request only. A `payment_result` separately records provider
authorization, capture, or failure. Only a captured result may receive a
`settlement_confirmation`, which records settlement or reversal.

```text
rfq_open -> quoted -> quote_accepted -> approved -> ordered
                                          |
                         order_rejected <-+-> order_acknowledged
                                                   |
                                               fulfilling
                                                   |
                                               fulfilled -> invoiced -> payment_pending
                                                                         |
                                             payment_failed <- authorized/captured
                                                                         |
                                                               settled/reversed
```

## Disputes

After a purchase order exists, either party may open a dispute against a
lifecycle message. The dispute records category, description, and optional
amount without replacing the order or payment state. The counterparty resolves
the open dispute as accepted, rejected, partial, or withdrawn. ACN 0.1 supports
one open dispute per transaction; later versions may support parallel cases.
## Quotation negotiation

After a supplier quotation, the buyer may send `quotation_counteroffer`. Its
`quotationMessageId` and `inReplyTo` must identify the latest active supplier
quotation. Its currency, RFQ line references, units, and maximum quantities
remain constrained by the opening RFQ; prices and commercial terms may change.

The supplier may respond with a revised `quotation`. A revised quotation uses
the same quotation document shape but `inReplyTo` identifies the latest
counteroffer. Participants must strictly alternate. A managed implementation
must reject acceptance of a superseded or expired quotation. ACN Cloud limits
negotiation to 20 counteroffers per transaction to bound resource consumption;
direct implementations must publish any different limit during discovery.
# Returns and credits

After a buyer-opened dispute, a supplier MAY send `return_authorization`. The
authorization references the dispute and bounds returnable order lines, quantities,
units, and expiration. The supplier sends `return_receipt` after physically receiving
the goods, followed by `credit_note` referencing both the original invoice and return
receipt. A credit note does not rewrite settlement history; implementations maintain
a separate return/credit projection and reconcile the accounting adjustment.
