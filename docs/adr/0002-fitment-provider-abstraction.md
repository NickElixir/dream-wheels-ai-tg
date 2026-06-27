# ADR 0002: Fitment Provider Abstraction

## Status

Accepted — 2026-06-26.

## Context

Technical compatibility needs structured vehicle-fitment data. Provider coverage, commercial terms and parameter quality must be verified before product integration. Directly coupling routes and domain rules to a provider would create vendor lock-in.

## Decision

Use a provider-neutral interface that resolves a confirmed vehicle and returns a normalized fitment profile. Keep provider selection, coverage results, cache policy and known gaps in a follow-up ADR after discovery.

The compatibility engine consumes normalized structured data and deterministic rules. LLMs may normalize/explain data but must not be the source of compatibility truth.

## Consequences

- Providers can be evaluated or replaced behind an adapter.
- Raw response references and provider/version metadata are retained for auditability.
- Missing coverage maps to `unknown`, not an invented positive verdict.
