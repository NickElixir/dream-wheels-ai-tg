# Stage 2 VLM Wheel-Mask Filter: Micro Report

Date: 2026-05-13

## Executive Summary

We tested a two-stage wheel-mask pipeline:

1. **Roboflow/YOLO segmentation** proposes candidate wheel masks.
2. **Qwen VLM** receives the original image, a labeled candidate overlay, and candidate metadata, then returns candidate IDs to keep or reject.

The experiment confirms that a VLM filter can reject wet-road wheel reflections while keeping real physical wheels. On the test image, `Qwen3-VL-30B-A3B-Instruct` matched the `Qwen3-VL-235B-A22B-Instruct` quality benchmark and is the better default production candidate for now.

Recommended strategy:

```text
Default:   qwen/qwen3-vl-30b-a3b-instruct
Fallback:  qwen/qwen3-vl-235b-a22b-instruct
Trigger fallback when confidence is low or scene geometry is ambiguous.
```

## Test Image

The image contains two real visible wheels and multiple wet-road reflections.

![Original car image](assets/vlm-mask-filter-experiment/cover-original.jpg)

## Candidate Overlay

Roboflow returned four `wheel` candidates when the pre-filter was changed from `top_n=2` to **no top-N limit**:

- `0`: front real wheel
- `1`: front wheel reflection
- `2`: road reflection / artifact
- `3`: rear real wheel

![Labeled wheel candidates](assets/vlm-mask-filter-experiment/cover-qwen3-30b-candidates-overlay.png)

Key learning: VLM filtering should receive **all reasonable wheel candidates**, not only the largest two. With `top_n=2`, the small rear wheel was excluded before the VLM could evaluate it.

## Model Comparison

All models were tested on the same Roboflow candidates with `--top-n 0`.

| Model | Keep IDs | Reject IDs | Confidence | Usage | Result |
|---|---:|---:|---:|---:|---|
| `qwen/qwen3-vl-235b-a22b-instruct` | `[0, 3]` | `[1, 2]` | `0.95` | `1037 in + 72 out` | Correct |
| `qwen/qwen3-vl-30b-a3b-instruct` | `[0, 3]` | `[1, 2]` | `0.93` | `1097 in + 91 out` | Correct |
| `qwen/qwen2.5-vl-72b-instruct` | `[0]` | `[1, 2, 3]` | `0.90` | `1275 in + 64 out` | Incorrect: rejected rear wheel |

The 30B Qwen3-VL model preserved both real wheels and rejected both reflection candidates. The older Qwen2.5-VL-72B model incorrectly rejected the rear wheel, despite being larger by parameter count.

## Final Mask From Qwen3-VL-30B

The final mask contains the two physical wheels only.

![Final mask from Qwen3-VL-30B](assets/vlm-mask-filter-experiment/cover-qwen3-30b-final-mask.png)

For comparison, the Qwen2.5-VL-72B run kept only the front wheel:

![Failure mask from Qwen2.5-VL-72B](assets/vlm-mask-filter-experiment/cover-qwen25-72b-failure-mask.png)

## Notes On The "Missing" Third Reflection

The left-side rear-wheel reflection is visible in the photo, but Roboflow did not return it as a `wheel` candidate. This is not a blocker for production: if Roboflow does not propose a mask, that region cannot leak into the final mask.

For debugging, the candidate overlay now adds bottom padding so candidates near the image border are easier to inspect.

## Current Implementation

The probe script is:

```text
scripts/vlm_mask_filter_probe.py
```

Example command:

```bash
.venv/bin/python scripts/vlm_mask_filter_probe.py \
  webapp/cover.jpg \
  tmp/roboflow-benchmark/wheels-tires-body_1/cover.roboflow.json \
  --top-n 0 \
  --model qwen/qwen3-vl-30b-a3b-instruct \
  --output-dir tmp/vlm-mask-filter/qwen3-30b-all
```

Required provider config:

```env
VLM_BASE_URL=https://api.zveno.ai/v1
VLM_API_KEY=...
VLM_MODEL=qwen/qwen3-vl-30b-a3b-instruct
```

## Dataset Recommendation

Current local dataset:

```text
/Users/nikolai/Documents/Dream Wheel AI/Ivan's Dataset/cars/
```

Observed contents:

- 40 image files, about 56 MB total.
- 14 top-level source images, including car photos and rim images.
- 26 generated/result images under `RESULTADOS/`.

Recommendation:

1. **Do not put the full raw image dataset directly into the main Git repo.**
   GitHub warns at files over 50 MiB and blocks files over 100 MiB; even smaller image datasets make clones slower over time. Use Git only for metadata, scripts, small curated examples, and benchmark reports.

2. **Use Roboflow for annotation and model-training datasets.**
   Roboflow is designed for uploading images, videos, and annotations into a project, supports web upload for datasets under 1,000 images, and supports dataset versions with preprocessing and augmentation. This is a better fit for wheel/tire/body masks than plain Git.

3. **Keep a local canonical dataset manifest.**
   Store a CSV/JSON manifest in Git with image IDs, source path, split, tags, license/consent status, and whether the image is a raw input or generated output. Keep the binary images in Roboflow, local storage, cloud storage, or Git LFS if we need repo-linked storage later.

4. **Separate raw inputs from generated outputs.**
   The `RESULTADOS/` images are useful for product QA, but they should not be mixed into a segmentation training set unless explicitly tagged as generated/synthetic outputs.

5. **Prefer collecting real photos over scraping the internet.**
   For this task, the hard cases are domain-specific: wet roads, reflections, occluded wheels, dark wheels, side angles, low light, glossy floors, cropped cars, and aftermarket rims. Real user-like photos will be more valuable than generic internet images. Internet images can help with long-tail diversity, but only if licensing/usage rights are clear.

Near-term target:

```text
50-100 curated real car photos
  -> tag reflection/lighting/angle conditions
  -> run Roboflow candidates
  -> run Qwen3-VL-30B filter
  -> manually review keep/reject decisions
  -> escalate failures to Qwen3-VL-235B
```

## References

- Roboflow data upload docs: https://docs.roboflow.com/datasets/adding-data
- Roboflow dataset versions: https://docs.roboflow.com/datasets/dataset-versions
- Roboflow augmentation guidance: https://docs.roboflow.com/datasets/dataset-versions/image-augmentation
- GitHub large file guidance: https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github

## Appendix: Negative Examples And Current Risk Status

### Dataset Naming

The downloaded Roboflow Universe dataset should be treated as a **Stage 1.5 candidate-segmentation sanity dataset**, not as the final Stage 2 VLM benchmark.

```text
Source dataset: wheeltirebody/wheels-tires-body
Downloaded version: 2
Local path: /private/tmp/dw-roboflow-stage2/wheels-tires-body-v2-coco
Roboflow project copy: the-hishnik/dream-wheels-stage2-wheel-benchmark
Stage label: Stage 1.5 - wheel candidate sanity / negative examples
```

This dataset is useful for checking whether the Roboflow candidate stage proposes wheel masks on normal car images and avoids firing on images where only `body`/`tire` are annotated. It is not sufficient to prove reflection handling.

### Stage 1.5 Sanity Benchmark Result

We ran the current Roboflow candidate model on all 125 images:

```bash
.venv/bin/python scripts/roboflow_benchmark.py \
  /private/tmp/dw-roboflow-stage2/wheels-tires-body-v2-coco \
  --model-id wheels-tires-body/1 \
  --classes wheel \
  --top-n 0 \
  --output-dir tmp/stage15-wheel-candidate-benchmark
```

Summary against the COCO annotations at the image level:

| Metric | Result |
|---|---:|
| Total images | 125 |
| Images with ground-truth `wheel` | 82 |
| Images without ground-truth `wheel` | 43 |
| True positives | 79 |
| True negatives | 43 |
| False positives | 0 |
| False negatives | 3 |
| Image-level accuracy | 97.6% |
| Wheel-image detection rate | 96.3% |
| No-wheel negative pass rate | 100.0% |

Interpretation:

- The current Roboflow model is a good candidate generator on this dataset.
- It did not produce wheel candidates on the 43 no-wheel negative examples.
- It missed wheel candidates on 3 images that had wheel annotations.
- This is an image-level sanity check, not a pixel-level mask-IoU evaluation.

### Negative Examples: Current Coverage

Current negative coverage is uneven:

| Negative type | Current status | Notes |
|---|---|---|
| Body-only / no-wheel car views | Covered by Stage 1.5 dataset | 43 no-wheel images passed with no wheel false positives. |
| Tire/body vs wheel confusion | Partially covered | Dataset includes `body`, `tire`, and `wheel`; useful for candidate sanity. |
| Wet-road reflections | Weak coverage | The synthetic/stylized `cover.jpg` is currently the main validated case. |
| Glossy floor / showroom reflections | Not enough coverage | Needs a dedicated hard-case set. |
| Shadows shaped like wheels | Not enough coverage | Needs real user-like photos. |
| Background vehicles / background wheels | Partially covered | Some dataset images include multiple cars, but not a controlled benchmark. |
| Cropped or partial wheels | Partially covered | Present in dataset, but no separate metric yet. |
| Night / low-light / neon glare | Weak coverage | `cover.jpg` covers one stylized example only. |
| Generated/synthetic outputs | Kept separate | Ivan's `RESULTADOS/` should not be mixed into raw training/benchmark data unless explicitly tagged. |

### Pipeline Risks

The main risk is **candidate recall**. If Roboflow does not propose a physical wheel mask, the VLM cannot recover it. The VLM only selects from existing candidate IDs; it does not draw masks.

Other current risks:

- **Top-N truncation risk:** using `top_n=2` dropped the small rear wheel in the cover experiment. Stage 2 should pass all reasonable wheel candidates after class/min-area filtering.
- **Reflection hard cases are under-tested:** the current success on wet-road reflections is promising but based on one strong example.
- **Pixel-level quality is not yet measured:** the Stage 1.5 benchmark checks whether at least one wheel candidate exists, not mask IoU or wheel completeness.
- **Dataset domain mismatch:** Universe images are useful but skew toward internet/tuning/showcase photos. Telegram user photos may be blurrier, darker, more compressed, and less centered.
- **Class semantics mismatch:** some datasets annotate `tire`, some annotate `wheel`, some annotate rim-like regions. We need a consistent definition for the final inpainting mask.
- **Provider/model drift:** OpenAI-compatible providers can change routing, model availability, pricing, or output formatting. The script should keep JSON validation and fallback behavior strict.
- **Privacy and licensing:** user photos should not be uploaded to public datasets; internet images need clear usage rights.

### Current Gaps Before MVP Stage 2 Confidence

Before calling Stage 2 production-ready, we still need:

1. A dedicated **Stage 2 hard-negative benchmark** with 30-50 images containing wet roads, reflections, glossy floors, shadows, night scenes, and background wheels.
2. A batch VLM evaluation script that runs `Qwen3-VL-30B` across benchmark images and stores keep/reject decisions in a reviewable CSV/JSON.
3. Manual review labels for candidate decisions:
   - physical wheel,
   - reflection,
   - shadow,
   - background wheel,
   - body/tire artifact,
   - missed physical wheel.
4. Pixel-level mask quality checks for final masks, at least on a small manually reviewed subset.
5. Escalation logic:

```text
Qwen3-VL-30B default
  -> if confidence is low, no candidates are kept, or scene has reflection-like geometry
  -> retry with Qwen3-VL-235B
```

### Practical Next Step

Use the Stage 1.5 dataset to validate candidate generation, but build a separate Stage 2 hard-negative set. The minimum useful next benchmark is:

```text
30-50 hard images
  10 wet-road reflections
  10 glossy floor / showroom reflections
  10 low-light or night images
  5-10 cropped/occluded wheels
  5-10 background-wheel or multi-car scenes
```

The Stage 1.5 result is encouraging, but it does not replace this hard-negative benchmark.
