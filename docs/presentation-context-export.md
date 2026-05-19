# Dream Wheels AI — Presentation Context Export

Date: 2026-05-14
Repository path: `/Users/nikolai/Documents/GitHub/dream-wheels-ai-quality-stage2-vlm-filter`
Current branch: `feature/ai-quality-stage2-vlm-filter`
Current HEAD: `536e686 docs(ai): add stage2 dataset handoff pdf`

## Copy/Paste Prompt For The Next Chat

Use this repository context to prepare an English presentation about the Dream Wheels AI quality work, especially the Stage 2 VLM wheel-mask filter. Chat with me in Russian, but all presentation text, slide titles, chart labels, and diagrams must be in English. Make slides visually clean: check that text does not overlap, does not leave boxes, and remains readable at 16:9 presentation size.

Primary story:

1. Dream Wheels AI lets users upload a car photo and wheel/rim photo, then returns an AI-remixed image with the new wheels.
2. The current product backend is a Telegram bot + FastAPI worker pipeline using Redis, Supabase/Postgres/Storage, and Reve API.
3. The AI quality work focuses on wheel mask quality. Stage 1/1.5 uses Roboflow/YOLO segmentation to propose wheel candidates.
4. Stage 2 adds a VLM filter: Roboflow/YOLO proposes candidate masks, cheap class/area filters remove obvious junk, Qwen VLM sees the original image plus a labeled candidate overlay and metadata, then returns keep/reject candidate IDs. The backend combines only kept masks.
5. The key experiment on `cover.jpg` showed why top-2 truncation is risky: it can drop the small real rear wheel before the VLM sees it. Stage 2 should pass all reasonable wheel candidates after class and min-area filtering.
6. On the initial reflection case, Qwen3-VL-30B kept real wheels `[0, 3]` and rejected reflections/artifacts `[1, 2]`, matching Qwen3-VL-235B quality. Qwen2.5-VL-72B failed by rejecting the rear wheel.
7. Stage 2 is promising but not production-proven yet. It needs a dedicated hard-negative benchmark of 30-50 images minimum, with a recommended first target of 50 reviewed images.

Important slide asset already prepared:

- `docs/assets/stage2-vlm-filter-pipeline.png` — 1920x1080 English slide-ready diagram with `cover.jpg` example, candidate overlay, final mask, and VLM keep/reject decisions.
- `docs/assets/stage2-vlm-filter-pipeline.svg` — editable source.

## Current Worktree Status

Untracked files created for the presentation:

```text
docs/assets/stage2-vlm-filter-pipeline.png
docs/assets/stage2-vlm-filter-pipeline.svg
```

No committed changes were made in this handoff export.

There is one stash:

```text
stash@{Thu May 14 10:33:20 2026}: On main: yookassa-payments-staging-wip
```

## Key Presentation Assets

Use these visuals:

| Asset | Purpose |
|---|---|
| `docs/assets/stage2-vlm-filter-pipeline.png` | Main Stage 2 pipeline slide, 16:9, English labels |
| `docs/assets/stage2-vlm-filter-pipeline.svg` | Editable vector source for the same slide |
| `docs/assets/vlm-mask-filter-experiment/cover-original.jpg` | Original `cover.jpg` example with wet-road reflections |
| `docs/assets/vlm-mask-filter-experiment/cover-qwen3-30b-candidates-overlay.png` | Candidate overlay with IDs |
| `docs/assets/vlm-mask-filter-experiment/cover-qwen3-30b-final-mask.png` | Correct final mask from Qwen3-VL-30B |
| `docs/assets/vlm-mask-filter-experiment/cover-qwen25-72b-failure-mask.png` | Failure comparison: Qwen2.5-VL-72B kept only the front wheel |
| `webapp/cover.jpg` | Product/demo cover image, same 640x360 base scene |

The generated pipeline diagram has already been visually checked after export:

- English-only visible text.
- 1920x1080 PNG.
- Main labels fit inside boxes.
- The Roboflow block was corrected to show `Roboflow` and `YOLO wheel candidates`.

## Core Stage 2 Findings

Source: `docs/ai-quality-stage2-vlm-filter-experiment.md`

Pipeline tested:

```text
Roboflow / YOLO segmentation
  -> wheel candidate masks with IDs
  -> VLM sees original image + labeled overlay + candidate metadata
  -> VLM returns keep/reject candidate IDs
  -> backend combines selected masks
```

Experiment image:

- Contains two real visible wheels.
- Contains multiple wet-road reflections.
- Roboflow returned four `wheel` candidates after removing top-N truncation.

Candidate interpretation:

| ID | Meaning |
|---:|---|
| 0 | front real wheel |
| 1 | front wheel reflection |
| 2 | road reflection / artifact |
| 3 | rear real wheel |

Main lesson:

```text
Stage 2 should pass all reasonable wheel candidates to the VLM after class/min-area filtering.
Do not use top_n=2 for Stage 2 filtering.
```

Model comparison:

| Model | Keep IDs | Reject IDs | Confidence | Result |
|---|---:|---:|---:|---|
| `qwen/qwen3-vl-235b-a22b-instruct` | `[0, 3]` | `[1, 2]` | `0.95` | Correct |
| `qwen/qwen3-vl-30b-a3b-instruct` | `[0, 3]` | `[1, 2]` | `0.93` | Correct |
| `qwen/qwen2.5-vl-72b-instruct` | `[0]` | `[1, 2, 3]` | `0.90` | Incorrect: rejected rear wheel |

Recommended runtime strategy:

```text
Default:  qwen/qwen3-vl-30b-a3b-instruct
Fallback: qwen/qwen3-vl-235b-a22b-instruct
Trigger fallback when confidence is low or scene geometry is ambiguous.
```

Important caveat:

If Roboflow does not propose a physical wheel candidate, the VLM cannot recover it. The VLM selects IDs; it does not draw pixel masks.

## Stage 1.5 Candidate Sanity Benchmark

Source: `docs/ai-quality-stage2-vlm-filter-experiment.md`

Roboflow Universe dataset:

```text
Source dataset: wheeltirebody/wheels-tires-body
Downloaded version: 2
Local path: /private/tmp/dw-roboflow-stage2/wheels-tires-body-v2-coco
Roboflow project copy: the-hishnik/dream-wheels-stage2-wheel-benchmark
Stage label: Stage 1.5 - wheel candidate sanity / negative examples
```

Benchmark command:

```bash
.venv/bin/python scripts/roboflow_benchmark.py \
  /private/tmp/dw-roboflow-stage2/wheels-tires-body-v2-coco \
  --model-id wheels-tires-body/1 \
  --classes wheel \
  --top-n 0 \
  --output-dir tmp/stage15-wheel-candidate-benchmark
```

Results:

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

- Roboflow is a good candidate generator on this sanity dataset.
- It did not produce wheel candidates on 43 no-wheel negative examples.
- This is not enough to prove Stage 2 reflection handling.
- It is image-level, not pixel-level IoU.

## Stage 2 Hard-Negative Benchmark Requirements

Source: `docs/stage2-hard-negative-dataset-requirements.md`

Purpose:

```text
Can the pipeline keep real physical wheels and reject reflections, shadows,
background wheels, and other wheel-like artifacts?
```

Dataset name:

```text
dream-wheels-stage2-hard-negatives
```

Targets:

| Target | Size |
|---|---:|
| MVP minimum | 30-50 images |
| First useful target | 50 images |
| Pre-production target | 100-150 images |

Recommended 50-image bucket plan:

| Bucket | Count | Why |
|---|---:|---|
| Wet road / water reflections | 10 | Primary known failure mode |
| Glossy floor / showroom reflections | 8 | Similar reflection geometry |
| Night / low-light / neon glare | 8 | Hard lighting |
| Shadows shaped like wheels | 5 | Prevent shadow leakage |
| Background vehicles / background wheels | 7 | Avoid selecting non-user-car wheels |
| Cropped / partial / occluded wheels | 6 | Common user-photo failure mode |
| Clean ordinary car photos | 6 | Baseline control group |

Candidate labels:

```text
physical_wheel
reflection
shadow
background_wheel
body_or_tire_artifact
other_artifact
uncertain
```

MVP metric targets:

| Metric | MVP Target |
|---|---:|
| Physical wheel candidate keep accuracy | >= 90% |
| Reflection candidate rejection accuracy | >= 85% |
| Background wheel rejection accuracy | >= 85% |
| Image-level final mask acceptable rate | >= 85% |
| Critical failure rate | <= 5% |

Candidate generator requirement:

```text
Roboflow should propose at least one candidate for each visible physical wheel
in >= 90% of benchmark images.
```

## Vehicle Recognition / Fitment RAG Context

Source: `docs/vehicle-recognition-rag-architecture.md`

This is not the main Stage 2 mask-filter slide, but it is useful as the next AI quality direction.

Goal:

- Identify make/model/generation/year range/body style from a user image.
- Retrieve fitment data.
- Use reference images to improve VLM reranking.
- Eventually guide compatible wheel sizes and rendering constraints.

Proposed architecture:

```text
User photo
  -> VLM produces candidate vehicle identities
  -> Wheel Size API retrieves structured metadata and reference images
  -> VLM compares user photo against references
  -> final ranked candidate with confidence
  -> fitment lookup and render preparation
```

Recommendation:

- Fine-tuned classifier is best for narrow, well-known catalogs.
- Qwen VLM + Wheel Size API RAG is better for broad coverage and long-tail vehicles.
- Long-term hybrid approach is best.

## Product / System Context

Source: `README.md` and `docs/architecture.md`

Dream Wheels AI product:

```text
User sends car photo + wheel/rim photo
  -> backend creates a job
  -> worker calls Reve image remix
  -> user receives rendered car image with new wheels
```

Current stack:

- Python 3.12.
- FastAPI + Uvicorn.
- Telegram bot via `python-telegram-bot`.
- Supabase/Postgres via `asyncpg`.
- Upstash Redis for queue, bot session cache, and rate limit counters.
- Supabase Storage for raw and result images.
- Reve API for image remix.
- Render hosting.
- Vercel static WebApp prototype.

Important endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /health` | basic uptime check |
| `GET /health/full` | full keep-alive check including DB/Redis on some branches |
| `POST /jobs` | Telegram URL-based job creation |
| `POST /jobs/upload` | WebApp binary upload flow |
| `GET /jobs/{job_id}` | job status polling |

Current high-level flow:

```text
Telegram/WebApp
  -> FastAPI job endpoint
  -> Postgres job row
  -> Redis job queue
  -> Worker
  -> Storage input download
  -> Reve API remix
  -> Storage result upload
  -> Postgres status update
  -> client polling returns final URL
```

## Important Scripts

| Script | Purpose |
|---|---|
| `scripts/roboflow_probe.py` | Probe one image with a Roboflow segmentation model |
| `scripts/roboflow_benchmark.py` | Run candidate benchmark on a folder/dataset |
| `scripts/vlm_mask_filter_probe.py` | Stage 2 VLM filter probe: original + overlay + metadata -> keep/reject IDs -> final mask |
| `scripts/download_yolo_seg.py` | YOLO segmentation model download helper |

Stage 2 probe example:

```bash
.venv/bin/python scripts/vlm_mask_filter_probe.py \
  webapp/cover.jpg \
  tmp/roboflow-benchmark/wheels-tires-body_1/cover.roboflow.json \
  --top-n 0 \
  --model qwen/qwen3-vl-30b-a3b-instruct \
  --output-dir tmp/vlm-mask-filter/qwen3-30b-all
```

VLM provider config:

```env
VLM_BASE_URL=https://api.zveno.ai/v1
VLM_API_KEY=...
VLM_MODEL=qwen/qwen3-vl-30b-a3b-instruct
```

Provider strategy:

- Keep the VLM provider OpenAI-compatible.
- Do not hard-code Alibaba Cloud.
- Candidate providers discussed: ZvenoAI, PaiAPI, VEGA API, AfonAI, OpenRouter.

## Branch Context

The table below is based on local branch state. `Behind main` means commits present on `main` but not on the branch; `Ahead of main` means commits present on the branch but not on `main`.

| Branch | Behind main | Ahead of main | HEAD | Purpose / interpretation |
|---|---:|---:|---|---|
| `main` | 0 | 0 | `0465b6a feat(i18n): add English interface` | Current production/release baseline |
| `staging/robokassa-payments` | 0 | 0 | `0465b6a feat(i18n): add English interface` | Same commit as `main`; staging branch name reserved for payments work |
| `feature/ai-quality-stage2-vlm-filter` | 31 | 8 | `536e686 docs(ai): add stage2 dataset handoff pdf` | Current AI quality Stage 2 branch; contains VLM mask filter probe, docs, datasets requirements |
| `feature/ai-quality-stage1` | 31 | 5 | `492d22e chore(cv): default Roboflow masks to wheels` | Roboflow/YOLO wheel candidate generation foundation |
| `feature/webapp-backend-integration` | 37 | 0 | `814da8b feat(jobs): wire worker to handle webapp source + storage RLS migration` | WebApp upload integration into backend and storage |
| `feature/webapp-vercel-prototype` | 36 | 0 | `3eaf61a fix(webapp): replace mock result image with honest demo placeholder` | Vercel prototype for Telegram WebApp UI |
| `feature/webapp-real-fetch` | 27 | 0 | `9b8777a chore: add .vercel and .env*.local to .gitignore, enable supabase mcp write access` | WebApp real fetch / Vercel env work |
| `feature/architecture-diagrams-readability` | 42 | 0 | `198e102 feat: /health/full endpoint + keep-alive setup guide` | Architecture diagrams, health endpoint, keep-alive docs |
| `debug/webapp-submit-log` | 18 | 0 | `26d9f47 chore(webapp): log submit state to debug 422` | Debug branch for WebApp submit 422 diagnostics |
| `fix/init-data-optional` | 25 | 0 | `2971f6d fix(jobs): accept empty init_data form field (browser testing)` | Browser testing fix for empty Telegram initData |
| `fix/render-cold-start-ping` | 23 | 0 | `1bcca96 fix(webapp): guard against null files before upload` | Render cold-start and upload guard fixes |
| `fix/single-screen-upload` | 13 | 2 | `0d3a690 Revert "feat(webapp): add result download button"` | Single-screen upload WebView stability direction |
| `fix/webapp-blob-persistence` | 17 | 0 | `f5af6e4 fix(webapp): persist file bytes as Blob to survive iOS Telegram WebView transitions` | iOS Telegram WebView file persistence fix |
| `fix/webapp-error-display` | 26 | 0 | `012cd8b fix(webapp): show readable FastAPI validation errors instead of [object Object]` | Better WebApp error rendering |
| `dev` | 31 | 0 | `23cf8a8 Merge pull request #4 from NickElixir/feature/webapp-backend-integration` | Older integration branch |
| `test` | 54 | 0 | `2857fd8 fix: lazy Redis client init in bot.py` | Older test/staging branch |

Remote branches mirror the local branch names under `origin/*`; `origin/HEAD` points to `origin/main`.

Recent all-branch commit landmarks:

```text
0465b6a main/staging: feat(i18n): add English interface
536e686 feature/ai-quality-stage2-vlm-filter: docs(ai): add stage2 dataset handoff pdf
4eab356 feature/ai-quality-stage2-vlm-filter: feat(ai): add stage2 vlm mask filter probe
691ff93 feature/ai-quality-stage2-vlm-filter: docs(ai): outline vehicle recognition RAG architecture
492d22e feature/ai-quality-stage1: chore(cv): default Roboflow masks to wheels
a3772d4 feature/ai-quality-stage1: feat(cv): benchmark Roboflow wheel masks
605f301 feature/ai-quality-stage1: chore(cv): add Roboflow probe tooling
950df77 feature/ai-quality-stage1: feat(cv): add YOLO wheel segmentation scaffold
b4212ce feature/ai-quality-stage1: feat(ai): add rim-aware remix prompts
```

## Suggested Presentation Outline

Recommended deck language: English.

1. **Problem / Product Context**
   - Dream Wheels AI: user uploads car + wheel, receives rendered result.
   - Quality bottleneck: wheel masks can include reflections, shadows, or background wheels.

2. **Current Product Architecture**
   - Telegram/WebApp -> FastAPI -> Redis queue -> Worker -> Reve API -> Storage -> status polling.
   - Keep this slide high-level.

3. **Why Wheel Mask Filtering Matters**
   - Bad masks leak artifacts into the final render.
   - Reflections are visually similar to wheels.

4. **Stage 1 / 1.5 Candidate Generation**
   - Roboflow/YOLO proposes wheel masks.
   - Stage 1.5 sanity benchmark: 125 images, 97.6% image-level accuracy, 0 false positives on 43 no-wheel negatives.
   - Limitation: candidate generator alone cannot reliably decide real wheel vs reflection.

5. **Stage 2 VLM Filter**
   - Use `docs/assets/stage2-vlm-filter-pipeline.png`.
   - Explain: original image + labeled overlay + metadata -> keep/reject IDs -> final mask.

6. **cover.jpg Experiment**
   - Roboflow returned four candidates.
   - Qwen3-VL-30B kept `[0, 3]`, rejected `[1, 2]`.
   - Qwen2.5-VL-72B failed by rejecting the rear wheel.

7. **Key Learning**
   - Do not truncate to top-2.
   - Pass all reasonable wheel candidates after class/min-area filtering.
   - VLM selects candidate IDs; it does not draw masks.

8. **Model Strategy**
   - Default: Qwen3-VL-30B.
   - Fallback: Qwen3-VL-235B for low confidence or ambiguous geometry.
   - Keep provider abstraction OpenAI-compatible.

9. **Validation Plan**
   - Stage 2 hard-negative benchmark: 50 images first useful target.
   - Buckets: wet roads, glossy floors, night glare, shadows, background wheels, occlusions, clean controls.
   - MVP targets: >=90% physical wheel keep accuracy, >=85% reflection rejection, <=5% critical failures.

10. **Next Steps**
    - Collect hard-negative dataset.
    - Add batch VLM evaluation script with reviewable CSV/JSON.
    - Manual candidate labels.
    - Pixel-level final mask checks.
    - Add escalation logic to larger model.

## Open Risks To Mention

- Candidate recall is the largest risk: missed physical wheels cannot be recovered by the VLM.
- Current reflection success is based on one strong `cover.jpg` case.
- Stage 1.5 benchmark is useful but not a hard-negative Stage 2 benchmark.
- Pixel-level mask quality is not yet measured.
- Telegram user photos may be blurrier, darker, more compressed, and less centered than benchmark images.
- Provider/model routing can drift; JSON validation and fallback logic should remain strict.
- User photos and internet photos need privacy/licensing controls.

## Current Files Most Relevant To Presentation

```text
README.md
docs/architecture.md
docs/ai-quality-stage2-vlm-filter-experiment.md
docs/stage2-hard-negative-dataset-requirements.md
docs/stage2-hard-negative-dataset-team-brief.md
docs/vehicle-recognition-rag-architecture.md
docs/assets/stage2-vlm-filter-pipeline.png
docs/assets/stage2-vlm-filter-pipeline.svg
docs/assets/vlm-mask-filter-experiment/cover-original.jpg
docs/assets/vlm-mask-filter-experiment/cover-qwen3-30b-candidates-overlay.png
docs/assets/vlm-mask-filter-experiment/cover-qwen3-30b-final-mask.png
docs/assets/vlm-mask-filter-experiment/cover-qwen25-72b-failure-mask.png
scripts/roboflow_probe.py
scripts/roboflow_benchmark.py
scripts/vlm_mask_filter_probe.py
```
