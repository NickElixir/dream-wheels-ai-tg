# Target Data Model

## Principle

The existing `jobs` table is the render-job aggregate for the current product. Evolve it through migrations; do not introduce an unrelated duplicate lifecycle table.

## Core tables

### `jobs`

Core lifecycle and provider metadata.

```text
id, user_id, status, created_at, updated_at
car_asset_id, rim_asset_id, result_asset_id
generation_provider, provider_request_id
generation_latency_ms, generation_cost
vehicle_identity_id, rim_spec_id, fitment_check_id
idempotency_key, prompt_version, pipeline_version
error_code, error_message
```

### `assets`

Durable file references, not browser-local URLs.

```text
id, owner_user_id, kind, storage_key, content_type
size_bytes, width, height, sha256, created_at
```

Kinds include `car_original`, `rim_original`, `result`, `wheel_mask`, `rim_crop` and `debug_artifact`.

### `vehicle_identities`

```text
id, make, model, generation, year, body, modification, drivetrain
source, confidence, is_user_confirmed, created_at, updated_at
```

### `rim_specs`

```text
id, brand, model, article, product_url
diameter_in, width_in, pcd, offset_et, center_bore_mm
bolt_seat_type, load_rating_kg
source, confidence, is_user_confirmed, created_at, updated_at
```

### `fitment_checks`

```text
id, job_id, vehicle_identity_id, rim_spec_id
provider, provider_version, raw_response_asset_id
status, confidence, reasons_json, warnings_json, missing_data_json
specialist_consultation_required, created_at
```

### `render_feedback`

```text
id, job_id, user_id
visual_result_accepted, rim_similarity_accepted
fitment_information_useful, failure_reason, comment, created_at
```

### Future tables

- `vehicle_fitment_profiles` — cached normalized profiles, provider/version/fetched/expiry.
- `generation_attempts` — internal retry history and quality scores.
- catalog and attribution tables — only after a structured product feed exists.

## Constraints and indexes

- foreign keys for every asset/spec/fitment relation;
- `jobs(user_id, created_at desc)` for history;
- unique idempotency scope appropriate to authenticated user;
- indexes on `jobs(status)` and provider cache key;
- migrations are the sole schema-change mechanism.

## Retention

Object storage retention and user deletion policy must be specified before storing debug artifacts or evaluation data. Keep only the minimum raw provider payload needed for support, audit and quality work.
