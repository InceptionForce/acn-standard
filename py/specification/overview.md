# ACN Standard 0.1

## Scope

ACN Standard defines portable commerce documents, their identifiers and the
legal transitions between them. It is independent of agent framework,
transport, hosting provider and system of record.

Version 0.1 defines `request_for_quote` and `quotation` documents.

## Non-goals

The standard does not define:

- how an organization is legally verified;
- how agents are discovered or ranked;
- how authorization policy is evaluated;
- how money is moved or held;
- how a managed provider stores transactions;
- how ERP-specific records are created.

## Conformance language

The words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative.

An implementation conforms to the procurement 0.1 profile when it:

1. accepts every valid conformance fixture;
2. rejects every invalid conformance fixture;
3. preserves unknown namespaced extensions;
4. enforces identifier, decimal, time and reference invariants; and
5. implements the lifecycle rules in `procurement-lifecycle.md`.
