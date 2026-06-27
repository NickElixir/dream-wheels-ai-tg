# ADR 0001: Durable Render History

## Status

Accepted — 2026-06-26.

## Context

The product needs render history, original/result comparison, support debugging, user feedback and a future evaluation dataset. Ephemeral files and browser-only state cannot support these requirements.

## Decision

Use the existing `jobs` record as the canonical render lifecycle. Persist source car image, source rim image and final result in durable object storage, referenced from Postgres through an asset model. Store status, provider request metadata, timestamps and failures in Postgres.

## Consequences

- History survives application reload and deployment.
- Storage permissions and retention need explicit policy.
- Future masks, crops and provider payloads can be linked without breaking the job contract.
- Database changes use idempotent migrations only.
