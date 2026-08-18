export const ACN_VERSION = "0.1" as const;
export const ACN_A2A_EXTENSION = "https://agentcommerce.network/extensions/commerce/v0.1";
export const ACN_MEDIA_TYPE = "application/vnd.acn.envelope+json;version=0.1";

export interface Envelope<T extends Record<string, unknown> = Record<string, unknown>> {
  specVersion: typeof ACN_VERSION;
  messageId: string;
  transactionId: string;
  documentType: string;
  sender: string;
  recipient: string;
  createdAt: string;
  expiresAt: string;
  idempotencyKey: string;
  document: T;
  inReplyTo?: string;
  signature?: {keyId: string; algorithm: "Ed25519"; createdAt: string; value: string};
}

export interface Submission {
  transactionId: string;
  messageId: string;
  status: string;
  duplicate: boolean;
}

export interface AgentProof {
  agentId: string;
  keyId: string;
  timestamp: string;
  nonce: string;
  signature: string;
}

export class AcnError extends Error {
  constructor(public status: number, public code: string, message: string, public retryable: boolean) {
    super(message);
  }
}

export function buildEnvelope<T extends Record<string, unknown>>(input: {
  documentType: string; sender: string; recipient: string; document: T;
  transactionId?: string; messageId?: string; idempotencyKey?: string;
  inReplyTo?: string; expiresInMs?: number; now?: Date;
}): Envelope<T> {
  const now = input.now ?? new Date();
  return {
    specVersion: ACN_VERSION,
    messageId: input.messageId ?? `msg_${crypto.randomUUID().replaceAll("-", "")}`,
    transactionId: input.transactionId ?? `txn_${crypto.randomUUID().replaceAll("-", "")}`,
    documentType: input.documentType,
    sender: input.sender,
    recipient: input.recipient,
    createdAt: now.toISOString(),
    expiresAt: new Date(now.getTime() + (input.expiresInMs ?? 900_000)).toISOString(),
    idempotencyKey: input.idempotencyKey ?? crypto.randomUUID(),
    document: input.document,
    ...(input.inReplyTo ? {inReplyTo: input.inReplyTo} : {}),
  };
}

/** Deterministic JSON for signing, excluding the signature itself.
 *  Mirrors `acn_standard.security.canonical_envelope` in the Python SDK. */
export function canonicalEnvelope(value: unknown): string {
  return canonical(value);
}

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.entries(value as Record<string, unknown>)
      // Code-point ordering, matching Python's json.dumps(sort_keys=True).
      // localeCompare is case-insensitive and locale-dependent, so it ordered
      // uppercase-initial keys differently and broke cross-language signatures.
      .filter(([key]) => key !== "signature").sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
      .map(([key, item]) => `${JSON.stringify(key)}:${canonical(item)}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function base64url(bytes: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(bytes))).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}

export async function signEnvelope<T extends Record<string, unknown>>(
  envelope: Envelope<T>, privateKey: CryptoKey, keyId: string,
): Promise<Envelope<T>> {
  const data = new TextEncoder().encode(canonical(envelope));
  const signature = await crypto.subtle.sign("Ed25519", privateKey, data);
  return {...envelope, signature: {keyId, algorithm: "Ed25519", createdAt: new Date().toISOString(), value: base64url(signature)}};
}

export class AcnClient {
  constructor(private baseUrl: string, private options: {retries?: number; timeoutMs?: number} = {}) {
    if (!baseUrl.startsWith("https://") && !baseUrl.startsWith("http://localhost")) throw new Error("ACN base URL must use HTTPS");
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  private async post(path: string, body: unknown, headers: Record<string, string>): Promise<any> {
    const attempts = (this.options.retries ?? 2) + 1;
    for (let attempt = 0; attempt < attempts; attempt++) {
      try {
        const response = await fetch(`${this.baseUrl}${path}`, {
          method: "POST", headers, body: JSON.stringify(body),
          signal: AbortSignal.timeout(this.options.timeoutMs ?? 30_000),
        });
        const value = await response.json();
        if (response.ok) return value;
        const retryable = [429, 502, 503, 504].includes(response.status);
        if (!retryable || attempt + 1 === attempts) throw new AcnError(response.status, value.code ?? value.error?.status ?? "acn.http.error", value.detail ?? value.error?.message ?? "ACN request failed", retryable);
      } catch (error) {
        if (error instanceof AcnError) throw error;
        if (attempt + 1 === attempts) throw new AcnError(0, "acn.transport.unavailable", String(error), true);
      }
      await new Promise(resolve => setTimeout(resolve, 250 * 2 ** attempt));
    }
  }

  async submit(envelope: Envelope): Promise<Submission> {
    const value = await this.post("/v1/messages", envelope, {"Content-Type": "application/json", "ACN-Version": ACN_VERSION});
    return {transactionId: value.transaction_id, messageId: value.message_id, status: value.status, duplicate: value.duplicate};
  }

  async submitA2A(envelope: Envelope, messageId = crypto.randomUUID()): Promise<Submission> {
    const body = {message: {messageId, contextId: envelope.transactionId, role: "ROLE_USER",
      parts: [{mediaType: ACN_MEDIA_TYPE, data: envelope}], extensions: [ACN_A2A_EXTENSION]}};
    const value = await this.post("/a2a/v1/message:send", body, {"Content-Type": "application/a2a+json", "A2A-Version": "1.0", "A2A-Extensions": ACN_A2A_EXTENSION});
    const result = value.message.parts[0].data;
    return {transactionId: result.transactionId, messageId: result.messageId, status: result.status, duplicate: result.duplicate};
  }

  async claimDeliveries(proof: AgentProof, limit = 10): Promise<any> {
    return this.post("/v1/delivery/claims", {proof, limit}, {"Content-Type": "application/json", "ACN-Version": ACN_VERSION});
  }

  async acknowledgeDelivery(deliveryId: string, proof: AgentProof): Promise<any> {
    return this.post(`/v1/delivery/${encodeURIComponent(deliveryId)}/ack`, {proof}, {"Content-Type": "application/json", "ACN-Version": ACN_VERSION});
  }

  async rejectDelivery(deliveryId: string, proof: AgentProof, reason: string): Promise<any> {
    return this.post(`/v1/delivery/${encodeURIComponent(deliveryId)}/reject`, {proof, reason}, {"Content-Type": "application/json", "ACN-Version": ACN_VERSION});
  }
}
