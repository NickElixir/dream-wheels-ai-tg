# Fitment API Contract v1

## Scope

API boundary for the future Detailed Fitment Check. It is provider-neutral and does not prescribe the final Fitment UI.

## Preconditions

- The caller is authenticated and owns the referenced VehicleIdentity/RimSetup/RenderJob.
- The request is initiated by a user action.
- A render job is optional and is never awaited by the fitment flow.

## Create a check

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

Validation:

- `trigger` is only `user_requested` in v1;
- validate object ownership server-side;
- snapshot VehicleIdentity and RimSetup at acceptance;
- reject duplicate active/equivalent requests through idempotency and input-version hash;
- do not debit paid units until the future pricing policy is explicitly approved.

## Read a check

```http
GET /fitment/checks/{check_id}
```

### Processing response

```json
{
  "id": "uuid",
  "execution_status": "queued",
  "verdict": null,
  "created_at": "2026-07-01T00:00:00Z"
}
```

### Completed response

```json
{
  "id": "uuid",
  "execution_status": "completed",
  "verdict": "compatible_with_conditions",
  "is_preliminary": true,
  "vehicle_identity_id": "uuid",
  "rim_setup_id": "uuid",
  "render_job_id": "uuid-or-null",
  "evaluated_at": "2026-07-01T00:00:00Z",
  "evidence_summary": {
    "overall_level": "E4",
    "missing_fields": [],
    "conflicting_fields": []
  },
  "reasons": [
    {
      "code": "CENTER_BORE_REQUIRES_RING",
      "severity": "warning",
      "axle": "front_and_rear",
      "fields": ["center_bore_mm"],
      "evidence_level": "E4"
    }
  ],
  "conditions": [
    {
      "code": "USE_SPECIFIED_CENTERING_RING",
      "axle": "front_and_rear"
    }
  ],
  "missing_fields": [],
  "versions": {
    "provider": "wheel_size",
    "provider_version": "2026-07-01",
    "engine_version": "v1",
    "rules_version": "v1"
  },
  "disclaimer_code": "PRELIMINARY_TECHNICAL_ASSESSMENT"
}
```

## Failed response

```json
{
  "id": "uuid",
  "execution_status": "failed",
  "verdict": null,
  "error": {
    "code": "PROVIDER_TIMEOUT",
    "retryable": true
  }
}
```

`failed` is operational. It must not be mapped to `unknown`.

## Stable machine codes

The API returns machine codes, not final Russian UI prose. Example codes:

```text
PCD_MISMATCH
CENTER_BORE_TOO_SMALL
CENTER_BORE_REQUIRES_RING
OFFSET_CLEARANCE_UNVERIFIED
BRAKE_CLEARANCE_UNVERIFIED
FASTENER_SPEC_REQUIRED
LOAD_RATING_REQUIRED
TYRE_PACKAGE_REQUIRED
MODIFIED_VEHICLE_REQUIRES_REVIEW
```

Frontend owns copy, placement and visual state after Fitment UX approval.

## Read history

```http
GET /fitment/checks?vehicle_identity_id=<uuid>&rim_setup_id=<uuid>
```

History must show the snapshot hash, execution state, verdict, evaluated time and versions. A new check is required when relevant input or rule/provider versions change.

## Security and audit

- Do not accept user identity, provider IDs or ownership from client-provided metadata.
- Do not expose provider raw payloads or signed asset URLs in standard responses.
- Persist provider/rules versions, input snapshot hash and idempotency key.
- Log operational errors separately from user-visible verdict reasons.

## Open items deliberately deferred

- pricing and debit semantics;
- provider cache / ToS policy;
- final Fitment UI and disclaimer copy;
- retry and stale-result policy;
- multi-provider arbitration.
