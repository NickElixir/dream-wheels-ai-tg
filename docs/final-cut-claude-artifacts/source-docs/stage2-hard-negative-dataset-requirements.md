# Stage 2 Hard-Negative Dataset Requirements

Date: 2026-05-13

## Purpose

This dataset is for validating the **Stage 2 VLM wheel-mask filter**, not for training the first candidate segmentation model.

The Stage 2 pipeline is:

```text
Roboflow / YOLO segmentation
  -> wheel candidate masks with IDs
  -> VLM sees original image + labeled overlay + candidate metadata
  -> VLM returns keep/reject candidate IDs
  -> backend combines selected masks
```

The dataset must answer one question:

```text
Can the pipeline keep real physical wheels and reject reflections, shadows,
background wheels, and other wheel-like artifacts?
```

## Dataset Name

Recommended working name:

```text
dream-wheels-stage2-hard-negatives
```

This should be separate from:

- Stage 1 training data;
- Stage 1.5 candidate sanity data;
- generated product outputs such as `RESULTADOS/`.

## Minimum Size

For the next MVP validation pass:

```text
30-50 images minimum
```

Recommended first useful target:

```text
50 images
```

Pre-production target:

```text
100-150 images
```

## Required Image Buckets

For a 50-image MVP benchmark:

| Bucket | Count | Why |
|---|---:|---|
| Wet road / water reflections | 10 | Primary known failure mode. |
| Glossy floor / showroom reflections | 8 | Similar reflection geometry, different environment. |
| Night / low-light / neon glare | 8 | Hard visual conditions and bright highlights. |
| Shadows shaped like wheels | 5 | Prevent shadow masks from leaking into final output. |
| Background vehicles / background wheels | 7 | Avoid selecting wheels that are not on the user car. |
| Cropped / partial / occluded wheels | 6 | Common user-photo failure mode. |
| Clean ordinary car photos | 6 | Baseline control group. |

It is fine if one image belongs to multiple buckets, but the manifest should include all applicable tags.

## Image Requirements

Each image should:

- contain a car or car-like target object;
- be representative of user-submitted Telegram photos where possible;
- preserve the original aspect ratio and resolution where possible;
- avoid heavy manual edits unless explicitly tagged as synthetic/generated;
- have clear licensing or consent status;
- be stored outside the Git repository unless it is a tiny curated example.

Preferred sources:

1. Real test-user/team photos with permission.
2. Parking-lot, street, showroom, garage, and wet-road photos collected for this benchmark.
3. Video frames from permitted videos.
4. Public internet images only when license/usage rights are clear.

Avoid mixing in generated AI outputs unless the image is explicitly tagged as synthetic.

## Required Labels

This benchmark does not require full pixel-perfect annotation for every object at first. It does require reviewable labels for candidate decisions.

For each Roboflow candidate mask, label one of:

```text
physical_wheel
reflection
shadow
background_wheel
body_or_tire_artifact
other_artifact
uncertain
```

At the image level, label:

```text
has_reflection
has_shadow
has_background_vehicle
has_cropped_wheel
has_occlusion
lighting_condition
view_angle
expected_visible_wheel_count
```

## Manifest Schema

Store the manifest in Git, but keep the binary image files in Roboflow, local storage, cloud storage, or Git LFS if needed.

Recommended CSV columns:

```text
image_id,
source_uri,
source_type,
license_or_consent,
split,
tags,
lighting_condition,
view_angle,
expected_visible_wheel_count,
has_reflection,
has_shadow,
has_background_vehicle,
has_cropped_wheel,
has_occlusion,
notes
```

Candidate-level review output should use a second file:

```text
image_id,
candidate_id,
candidate_class,
candidate_bbox_xyxy,
candidate_area_ratio,
model_keep,
model_confidence,
human_label,
review_notes
```

## Evaluation Metrics

Primary Stage 2 metrics:

| Metric | MVP Target |
|---|---:|
| Physical wheel candidate keep accuracy | >= 90% |
| Reflection candidate rejection accuracy | >= 85% |
| Background wheel rejection accuracy | >= 85% |
| Image-level final mask acceptable rate | >= 85% |
| Critical failure rate | <= 5% |

Critical failures:

- no physical wheel kept when a visible wheel candidate exists;
- reflection/shadow dominates the final mask;
- background vehicle wheel selected instead of the user car wheel;
- VLM returns invalid JSON or unusable candidate IDs.

## Candidate Generator Requirements

Before evaluating VLM quality, verify candidate recall:

```text
Roboflow should propose at least one candidate for each visible physical wheel
in >= 90% of benchmark images.
```

Important implementation rule:

```text
Do not use top_n=2 for Stage 2 filtering.
Pass all reasonable wheel candidates after class and minimum-area filtering.
```

The `cover.jpg` experiment showed that `top_n=2` can drop a small real rear wheel before the VLM sees it.

## Model Testing Plan

Default model:

```text
qwen/qwen3-vl-30b-a3b-instruct
```

Quality fallback:

```text
qwen/qwen3-vl-235b-a22b-instruct
```

Evaluation flow:

```text
Run Roboflow candidates
  -> generate labeled overlay
  -> run Qwen3-VL-30B
  -> save JSON decision
  -> manually review candidate labels
  -> retry failure/low-confidence cases with Qwen3-VL-235B
```

Escalate to the larger model when:

- confidence is below threshold;
- no candidates are kept;
- all candidates are rejected despite expected visible wheels;
- reflection-like geometry is present;
- output JSON is invalid or incomplete.

## What Counts As Done

Stage 2 MVP validation can be considered passed when:

1. The hard-negative dataset has at least 50 reviewed images.
2. Candidate-level labels exist for all Roboflow wheel candidates.
3. Qwen3-VL-30B meets the MVP metric targets.
4. Qwen3-VL-235B fallback improves most low-confidence or failed cases.
5. Remaining failures are documented with clear categories and next actions.

## Current Status

Current status as of 2026-05-13:

- Stage 2 architecture is validated on the initial `cover.jpg` reflection case.
- Qwen3-VL-30B matched Qwen3-VL-235B on that case.
- Stage 1.5 candidate sanity dataset was created from `wheeltirebody/wheels-tires-body` v2.
- Stage 1.5 benchmark result: 125 images, 43 no-wheel negatives, 0 false positives, 3 false negatives.
- A dedicated Stage 2 hard-negative dataset has not been collected yet.

Conclusion:

```text
The branch is ready to publish as a Stage 2 research/prototype milestone.
Full Stage 2 MVP validation requires the hard-negative dataset described here.
```
