# Team Brief: Stage 2 Hard-Negative Dataset Task

Hi team,

We need to prepare a small hard-negative benchmark dataset for validating the Stage 2 VLM wheel-mask filter.

The goal is to collect **50 real-world car images** that stress the pipeline: wet-road reflections, glossy showroom floors, night glare, shadows, background wheels, cropped wheels, and occlusions. This dataset is not for general training yet; it is for checking whether the current pipeline can keep real physical wheels and reject reflections or other wheel-like artifacts.

Please follow the attached requirements document:

```text
stage2-hard-negative-dataset-requirements.pdf
```

Expected deliverables:

1. A Roboflow dataset/project named:

```text
dream-wheels-stage2-hard-negatives
```

2. Around 50 images distributed across the required buckets:

```text
10 wet-road reflections
8 glossy floor / showroom reflections
8 night or low-light glare
5 wheel-shaped shadows
7 background vehicles / background wheels
6 cropped, partial, or occluded wheels
6 clean ordinary car photos as controls
```

3. A manifest with image-level tags:

```text
image_id,
source_uri,
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

4. After candidate masks are generated, candidate-level review labels:

```text
physical_wheel
reflection
shadow
background_wheel
body_or_tire_artifact
other_artifact
uncertain
```

Success criterion for this task:

```text
We should be able to run the Roboflow -> Qwen3-VL-30B filter on these images
and manually review whether real wheels are kept while reflections/shadows/background wheels are rejected.
```

Please prioritize real user-like photos over generic internet images. Internet images are acceptable only when usage rights are clear. Do not mix generated AI outputs into this dataset unless they are explicitly tagged as synthetic.
