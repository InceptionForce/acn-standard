import assert from "node:assert/strict";
import test from "node:test";
import {webcrypto} from "node:crypto";
import {AcnClient, AcnError, buildEnvelope, canonicalEnvelope, signEnvelope} from "../dist/index.js";

if (!globalThis.crypto) globalThis.crypto = webcrypto;

test("buildEnvelope emits ACN wire names", () => {
  const value = buildEnvelope({documentType: "request-for-quote", sender: "agent:a",
    recipient: "agent:b", document: {}, now: new Date("2026-01-01T00:00:00Z")});
  assert.equal(value.specVersion, "0.1");
  assert.equal(value.createdAt, "2026-01-01T00:00:00.000Z");
  // Must satisfy the ACN 0.1 identifier grammar the reference validator enforces.
  assert.match(value.messageId, /^msg_[A-Za-z0-9_-]{8,128}$/);
  assert.match(value.transactionId, /^txn_[A-Za-z0-9_-]{8,128}$/);
});

test("canonicalization orders keys by code point, matching the Python SDK", () => {
  const ordered = canonicalEnvelope({document: {Total: "10.00", amount: "5.00"}});
  // Python's json.dumps(sort_keys=True) puts "Total" (U+0054) before "amount"
  // (U+0061); a case-insensitive sort would reverse them and break signatures.
  assert.equal(ordered, '{"document":{"Total":"10.00","amount":"5.00"}}');
});

test("signEnvelope creates a verifiable Ed25519 signature", async () => {
  const keys = await crypto.subtle.generateKey("Ed25519", true, ["sign", "verify"]);
  const envelope = buildEnvelope({documentType: "request-for-quote", sender: "agent:a",
    recipient: "agent:b", document: {currency: "USD"}});
  const signed = await signEnvelope(envelope, keys.privateKey, "key:test");
  assert.equal(signed.signature.algorithm, "Ed25519");
  assert.match(signed.signature.value, /^[A-Za-z0-9_-]+$/);
});

test("direct, A2A, and delivery methods use their formal endpoints", async t => {
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({url, body: JSON.parse(init.body)});
    if (url.endsWith("message:send")) return Response.json({message: {parts: [{data: {
      transactionId: "txn:1", messageId: "msg:1", status: "open", duplicate: false}}]}});
    if (url.endsWith("/v1/messages")) return Response.json({transaction_id: "txn:1",
      message_id: "msg:1", status: "open", duplicate: false});
    return Response.json({status: "ok"});
  };
  t.after(() => { globalThis.fetch = original; });
  const client = new AcnClient("https://acn.example", {retries: 0});
  const envelope = buildEnvelope({documentType: "request-for-quote", sender: "agent:a",
    recipient: "agent:b", document: {}});
  await client.submit(envelope);
  await client.submitA2A(envelope, "a2a-message");
  const proof = {agentId: "agent:b", keyId: "key:b", timestamp: "now", nonce: "n", signature: "s"};
  await client.claimDeliveries(proof);
  await client.acknowledgeDelivery("delivery/one", proof);
  await client.rejectDelivery("delivery/one", proof, "invalid");
  assert.deepEqual(calls.map(call => new URL(call.url).pathname), [
    "/v1/messages", "/a2a/v1/message:send", "/v1/delivery/claims",
    "/v1/delivery/delivery%2Fone/ack", "/v1/delivery/delivery%2Fone/reject",
  ]);
});

test("transient errors retry and preserve typed terminal failures", async t => {
  const original = globalThis.fetch;
  let count = 0;
  globalThis.fetch = async () => {
    count += 1;
    return count === 1 ? Response.json({detail: "busy"}, {status: 503}) :
      Response.json({transaction_id: "txn:1", message_id: "msg:1", status: "open", duplicate: false});
  };
  t.after(() => { globalThis.fetch = original; });
  await new AcnClient("https://acn.example", {retries: 1}).submit({});
  assert.equal(count, 2);

  globalThis.fetch = async () => Response.json({code: "acn.document.invalid", detail: "bad"}, {status: 422});
  await assert.rejects(() => new AcnClient("https://acn.example").submit({}),
    error => error instanceof AcnError && error.code === "acn.document.invalid" && !error.retryable);
});
