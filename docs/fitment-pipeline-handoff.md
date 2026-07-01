# Fitment Verdict Pipeline — Engineering Handoff

## Purpose

This document is the implementation handoff for the Fitment Verdict Pipeline. It captures the product and integration decisions already agreed with the Dream Wheels AI team.

Read together with:

```text
docs/product-roadmap.md
docs/adr/0002-fitment-render-integration.md
docs/fitment-schema.md
docs/fitment-verdict-evidence-rules.md
docs/fitment-api-contract-v1.md
```

## Product boundary

Dream Wheels AI has two independent pipelines:

```text
Rendering Pipeline
→ answers: “How will these wheels look on this car?”

Fitment Pipeline
→ answers: “What is known about the preliminary technical possibility of installation?”
```

A visual render is never proof of fitment. Fitment must not block or delay render creation.

## Agreed user flow

```text
User confirms vehicle and rim data
→ starts visual render
→ render runs independently
→ user explicitly requests Detailed Fitment Check
→ Fitment Pipeline evaluates and returns a preliminary verdict
```

Detailed provider search/check is **user initiated only**. Do not prefetch or trigger mass provider lookups automatically.

## Two distinct modes

### 1. Visual-support inference

Purpose: improve the rendering flow.

Allowed inputs:

- photos;
- OCR;
- VLM hints;
- basic user-entered data.

Output:

- extraction hints;
- suggested form values;
- render-oriented metadata.

It is **not** a technical compatibility verdict. Do not return `compatible`, `unknown`, etc. from this mode.

### 2. Detailed Fitment Check

Purpose: preliminary technical assessment.

Inputs:

- confirmed vehicle identity;
- rim SKU / manufacturer data whenever available;
- confirmed or trusted technical values;
- provider data and deterministic rules.

Output:

```text
compatible
compatible_with_conditions
unknown
incompatible
```

May later have separate pricing, but pricing/debit logic is not part of the current implementation scope.

## Canonical ownership model

Use shared domain entities; neither pipeline owns the other.

```text
RenderJob
├── vehicle_identity_id
├── rim_setup_id
└── immutable render_input_snapshot

RimSetup
├── front_rim_spec_id
├── rear_rim_spec_id
└── is_staggered

FitmentCheck
├── vehicle_identity_id
├── rim_setup_id
├── render_job_id nullable
├── immutable vehicle_snapshot
├── immutable rim_setup_snapshot
└── verdict / evidence / versions
```

`render_job_id` is optional. A detailed check may run without a render, and a render may exist without a check.

## Vehicle and rim model

### VehicleIdentity

Canonical fields:

```text
make
model
year
body nullable
generation nullable
modification nullable
market nullable
is_user_confirmed
provider_mappings nullable
field_provenance
```

Provider-specific slugs/IDs are populated after resolution and do not replace canonical vehicle fields.

### RimSpec

One RimSpec describes one wheel specification for one axle.

```text
brand nullable
model nullable
sku nullable
product_url nullable

bolt_count nullable
pcd_mm nullable
center_bore_mm nullable
wheel_diameter_in nullable
wheel_width_j nullable
offset_et_mm nullable
load_rating_kg nullable

fastener_system nullable
seat_type nullable
thread_diameter_mm nullable
thread_pitch_mm nullable
bolt_length_mm nullable

field_provenance
```

### PCD normalisation

Use numeric fields:

```text
bolt_count = 5
pcd_mm = 114.3
```

Derive `5x114.3` for display. Do not store separate conflicting string fields `pcd` and `bolt_pattern`.

### Staggered setup

Support separate front and rear specifications from the start:

```text
front_rim_spec_id
rear_rim_spec_id
is_staggered
```

For a square setup, both references may point to the same RimSpec.

## Evidence and provenance

Every field must be capable of carrying:

```json
{
  "value": "5x114.3",
  "source": "user_input | user_confirmed | manufacturer_sku | provider | ocr | vlm | unknown",
  "confidence": 0.0,
  "is_user_confirmed": false
}
```

Initial Sprint 2 values can mostly be `user_input` or `user_confirmed`, but do not design storage so later OCR/VLM/provider provenance requires a breaking migration.

Evidence levels:

```text
E0 unknown
E1 VLM/OCR suggestion
E2 user input, not yet confirmed
E3 user-confirmed or trusted provider value
E4 manufacturer SKU/technical document or exact audited provider profile
```

Never use E1/E2 alone to issue `compatible`.

## Verdict semantics and priority

```text
1. confirmed hard conflict
   → incompatible

2. no hard conflict but critical evidence missing or conflicting
   → unknown

3. sufficient evidence but explicit adaptation / verification is needed
   → compatible_with_conditions

4. sufficient evidence, no conditions
   → compatible
```

Operational check status is separate:

```text
queued | processing | completed | failed
```

Provider timeout, rate limit, parsing issue or technical failure is `failed`, not `unknown`.

## Rule baseline

### Confirmed hard conflicts

`incompatible` only with sufficiently trusted evidence:

- PCD / bolt count mismatch;
- wheel centre bore smaller than hub bore;
- confirmed wheel/brake/suspension/body interference;
- confirmed incompatible fastener system or seat with no known supported hardware package;
- wheel load rating below required load;
- confirmed tyre/rim package outside wheel maker range or confirmed interference;
- axle-specific conflict in a staggered configuration.

### Conditions

`compatible_with_conditions` requires specific, explainable conditions:

- known correct centering ring for a larger wheel bore;
- confirmed alternative hardware package with correct seat and engagement;
- provider/rules evidence requiring a specific spacer or additional clearance check;
- supported non-OEM tyre/wheel package with remaining physical installation check;
- validated staggered front/rear setup per axle.

Do not automatically recommend wobble bolts, redrilling, generic adapters, generic spacers, inferred bolt length, inferred seat type or inferred brake clearance.

### Unknown

Use `unknown` for incomplete or conflicting evidence, including:

- unknown PCD / DIA / ET where required;
- ambiguous vehicle generation/modification;
- missing tyre or clearance evidence for a non-OEM package;
- modified suspension, aftermarket brakes or body modifications without supported profile;
- low-confidence OCR/VLM only.

## API contract

Create check:

```http
POST /fitment/checks
Idempotency-Key: <uuid>
```

```json
{
  "vehicle_identity_id": "uuid",
  "rim_setup_id": "uuid",
  "render_job_id": "uuid-or-null",
  "trigger": "user_requested",
  "mode": "detailed"
}
```

Implementation requirements:

- verify ownership server-side;
- snapshot inputs when request is accepted;
- de-duplicate active/equivalent requests using idempotency and input-version hash;
- do not expose raw provider payloads in normal API responses;
- return machine reason/condition codes, not final Russian UI prose;
- store provider, engine and rule versions with every completed check.

## Expected deliverables from Fitment Pipeline work

1. Provider-agnostic domain models and adapters.
2. Vehicle resolution capable of writing provider mappings after canonical identity is known.
3. Rim normalisation with field provenance.
4. Deterministic rule engine implementing the taxonomy above.
5. Async FitmentCheck execution lifecycle.
6. API endpoints matching `docs/fitment-api-contract-v1.md`.
7. Versioned rule/provider evidence and auditable snapshots.
8. Golden tests for known compatible, conditional, unknown and incompatible cases.
9. Explicit provider ToS/cache/rate-limit policy proposal before production provider usage.

## Explicitly out of scope for the Fitment Pipeline owner

- final Fitment UI layout, Russian copy and placement;
- changing rendering flow semantics;
- blocking render creation;
- payment/debit implementation;
- presenting VLM/OCR guesses as technical verdicts;
- claiming installation guarantee or legal compliance.

## Open decisions requiring joint review before production

- provider ToS, cache duration and regional coverage;
- numeric tolerance policy, only where backed by authoritative data;
- stale/recheck policy when provider or rule version changes;
- detailed-check pricing and retry rules;
- final user-facing Fitment UI and disclaimer text;
- multi-provider arbitration.

## Definition of done for integration readiness

The Fitment Pipeline is ready to integrate when:

- a `FitmentCheck` can run from confirmed VehicleIdentity + RimSetup;
- it returns execution status separately from verdict;
- verdict carries machine-readable reasons, conditions, missing fields and versions;
- all checks use immutable snapshots;
- render creation remains unaffected;
- tests cover owner isolation, idempotency, provider failure, unknown evidence and a staggered setup;
- no final UI assumptions are embedded in the backend contract.
