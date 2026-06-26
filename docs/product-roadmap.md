# Product and Delivery Roadmap

## Goal

Dream Wheels AI combines two independent user outcomes:

1. **Visual fitment** — a generated image of the user's car with selected wheels.
2. **Technical compatibility** — a preliminary fitment verdict derived from confirmed vehicle data, wheel specifications and a structured fitment provider.

A visual result must never be presented as proof of technical compatibility.

## Delivery sequence

### Sprint 0 — durable render foundation

**Backend and database**

- Treat the existing `jobs` record as the canonical render job; evolve it instead of creating a second competing job entity.
- Store source images and result images in durable object storage.
- Persist storage object identifiers/URLs, provider request metadata, timestamps, status and error code.
- Keep idempotency for upload/create requests.
- Add a history endpoint backed by Postgres rather than browser state.

**Exit criteria**

- A completed or failed render remains visible after reload and deploy.
- Original car image, original rim image and final image can be retrieved for an authorized user.

### Parallel F0 — fitment provider discovery

- Evaluate candidate fitment data sources against a representative vehicle set.
- Record coverage, supported parameters, latency, terms, cache policy, price and gaps.
- Select a provider only through an ADR; domain code must remain provider-agnostic.

### Sprint 1 — cabinet dashboard

- Dashboard with balance, latest render, CTA and navigation to history/wallet.
- Read from durable render history and existing payment endpoints.

### Sprint 2 — create flow and structured input

Flow: upload car → upload rim → confirm vehicle → optional rim data → review → generate.

- Vehicle confirmation: make, model, year, body; generation/modification when needed.
- Optional rim fields: brand, model, SKU/article, product URL, diameter, width, PCD, ET, DIA.
- Input technical validation and self-check warnings only; no automatic AI rejection.

### Parallel F1 — fitment domain and rules engine

- Normalize vehicle identity, vehicle fitment profile, rim specifications and verdict.
- Implement deterministic checks for PCD, DIA, ET, width, diameter, fasteners and axle differences when available.
- Return `compatible`, `compatible_with_conditions`, `unknown` or `incompatible`.
- Add golden tests and source/version audit data.

### Sprint 3 — comparison, history and feedback

- Original/result toggle in render detail.
- Render history with states and repeat scenario.
- User feedback on visual similarity and usefulness.

### Parallel F2 — fitment UX integration

- Trigger a fitment check after vehicle and rim inputs are available.
- Do not block image generation.
- Show verdict, reasons, missing data and specialist disclaimer on result detail and history.

**Customer-development gate**

Run customer development after Sprint 3 + F2. The tested product is the complete value proposition: visual fitment + preliminary compatibility, not a standalone image generator.

### Sprint 4 — wallet redesign

- Balance, packages, invoice summary, receipt email and payment CTA.
- Do not advertise credit expiration until the backend implements it.
- Keep payment provider behavior out of this scope.

### Parallel F3 — catalog and partner recommendations

Requires a structured owned catalog or partner feed.

- Filter products by technical fitment.
- Rank by fit score, availability, visual similarity, price and commercial priority.
- Track impressions, clicks and leads.

### Sprint 5 — evaluation baseline

- Build a labelled evaluation dataset from consented/test cases.
- Benchmark generation providers by cost, latency, visual quality, wheel similarity and vehicle preservation.
- Keep expert labels separate from user feedback.

### Sprint 6 — soft input quality gate

- Add CV/VLM checks for blur, brightness, resolution, car/wheel visibility and rim front-face visibility.
- Show warnings; do not automatically reject uploads until measured evidence supports it.

### Sprint 7 — controlled rendering pipeline

- Wheel detection and segmentation.
- Mask/crop artifacts and render plan.
- Post-generation validation, one internal retry and provider fallback.
- Internal retries never consume additional user credits.

## Non-goals in the current block

- Email/phone login changes.
- Payment provider switching.
- Credit expiration implementation without separate approval.
- Hard fitment guarantees.
- Catalog recommendations without an auditable product feed.
