# ACN TypeScript SDK

Typed, zero-runtime-dependency helpers for ACN 0.1, including envelope construction,
Ed25519 Web Crypto signing, direct submission, and the formal A2A 1.0 binding.

```ts
import {AcnClient, buildEnvelope} from "@agent-commerce-network/sdk";

const envelope = buildEnvelope({
  documentType: "request-for-quote",
  sender: "agent:buyer",
  recipient: "agent:seller",
  document: {currency: "USD", lineItems: []},
});
const result = await new AcnClient("https://acn.example.com").submit(envelope);
```

Remote endpoints must use HTTPS; only `http://localhost` is accepted for development.
