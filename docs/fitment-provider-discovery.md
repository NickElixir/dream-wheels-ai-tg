# Fitment Provider Discovery

## Decision

The compatibility engine depends on a provider abstraction. No external provider is embedded in route handlers, database enums or rule logic. The selected implementation is recorded in a separate ADR after discovery.

## Discovery questions

For each candidate, verify:

- vehicle coverage for the target market and common generations/modifications;
- availability of PCD, DIA, ET, width, diameter, fastener data, load data and axle-specific profiles;
- distinction between OEM and aftermarket recommendations;
- API stability, latency, limits and failure modes;
- commercial terms, permitted caching and redistribution;
- production pricing and support model;
- whether raw responses can be retained for audit/debug.

## Representative test set

Use 30–50 vehicles covering:

- domestic market models;
- common Chinese brands;
- European, Japanese and Korean vehicles;
- multiple generations/restylings;
- body variants;
- vehicles with staggered front/rear fitment.

Manually validate 10–20 cases against trusted professional catalogues or specialist data. Record gaps rather than silently filling them with LLM output.

## Adapter contract

```text
resolve_vehicle(identity) -> normalized vehicle reference
get_fitment_profile(vehicle_reference) -> FitmentProfile
```

The normalized profile is cached with provider name, provider version, fetched time and expiry. Keep a raw response reference for auditability.

## Acceptance criteria

A provider can be selected for F1 only when:

- coverage and critical parameter completeness are measured;
- rate/cost assumptions are documented;
- error/timeout behavior is known;
- cache and licensing strategy is approved;
- known gaps have a `unknown` UX path.

## Output

Create an ADR containing the chosen provider, evidence, scope, known gaps, caching policy and conditions for reconsideration.
