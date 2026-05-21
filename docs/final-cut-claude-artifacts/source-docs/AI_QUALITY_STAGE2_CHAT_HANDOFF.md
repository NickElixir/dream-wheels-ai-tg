# AI Quality Stage 2 Chat Handoff

Date: 2026-05-12

## Current Branches and Worktrees

- Main worktree:
  - Path: `/Users/nikolai/Documents/GitHub/dream-wheels-ai-tg`
  - Current branch: `feature/ai-quality-stage2-vlm-filter`
  - Current HEAD: `691ff93 docs(ai): outline vehicle recognition RAG architecture`
  - Current untracked file: `.DS_Store`

- Main branch worktree:
  - Path: `/Users/nikolai/Documents/GitHub/dream-wheels-ai-tg-main`
  - Branch: `main`
  - Contains commit: `99f1bdc chore(vercel): commit project link metadata`

## Important Commits

- `605f301 chore(cv): add Roboflow probe tooling`
  - Added `scripts/roboflow_probe.py`.
  - Added `ROBOFLOW_API_KEY` to `.env.example`.
  - Added `tmp/` to `.gitignore`.

- `a3772d4 feat(cv): benchmark Roboflow wheel masks`
  - Added `scripts/roboflow_benchmark.py`.
  - Changed Roboflow default model to `wheels-tires-body/1`.
  - Added class/area/top-N filtering.
  - Saves JSON, mask, combined mask, overlay, and summary files.

- `492d22e chore(cv): default Roboflow masks to wheels`
  - Default mask class changed to `wheel`.
  - Default `top_n` changed to `2`.

- `691ff93 docs(ai): outline vehicle recognition RAG architecture`
  - Added `docs/vehicle-recognition-rag-architecture.md`.
  - Captures the proposed Qwen VLM + Wheel Size API RAG architecture.

## Roboflow Model Decision

Initial candidate:

- `tire-segmentation-eqoeu/5`
  - Classes: `wheel`, `rim`
  - Failed to detect anything on the stylized `webapp/cover.jpg`.

Selected current candidate:

- `wheels-tires-body/1`
  - Classes include `wheel`, `tire`, `body`.
  - On `webapp/cover.jpg`, it detected real wheels but also some reflections.
  - After wheel-only filtering, it selected `2` wheel candidates, but one was a reflection because it was larger than the real rear wheel.

Current conclusion:

- Roboflow/YOLO is useful for candidate masks.
- Simple `top_n` filtering is not enough for wet/reflection cases.
- Next stage should add VLM-based candidate selection or geometric position filtering.

## Current Roboflow Scripts

Probe one image:

```bash
.venv/bin/python scripts/roboflow_probe.py webapp/cover.jpg
```

Benchmark a folder:

```bash
.venv/bin/python scripts/roboflow_benchmark.py test-images \
  --model-id wheels-tires-body/1
```

Outputs:

```text
tmp/roboflow/
tmp/roboflow-benchmark/
```

Important files:

- `*.roboflow.json`
- `*.mask.png`
- `*.combined_mask.png`
- `*.overlay.png`
- `summary.csv`
- `summary.json`

## Qwen / VLM Direction

The preferred architecture is not to ask the VLM to draw pixel masks.

Instead:

```text
Roboflow / YOLO segmentation
  -> candidate masks with IDs
  -> Qwen VLM sees original image + labeled overlay + candidate metadata
  -> VLM returns keep/reject candidate IDs
  -> backend combines selected masks
```

Example target VLM output:

```json
{
  "keep_candidate_ids": [0, 2],
  "reject_candidate_ids": [1, 3],
  "reasoning_summary": "Candidate 3 is a road reflection, not a physical wheel."
}
```

## Qwen Model Discussion

For the wheel-mask VLM filter, only `VL` models are relevant.

Best quality candidate:

- `Qwen3-VL-235B-A22B-Instruct`
  - Strongest from the discussed list.
  - Arena / vision rank found around `31`, Elo around `1214.5` in one mirrored snapshot.
  - Use as quality benchmark or fallback for hard cases.

Practical production candidate:

- `Qwen2.5-VL-32B-Instruct`
  - Arena / vision rank found around `76`, Elo around `1120.2` in one mirrored snapshot.
  - Likely better cost/latency tradeoff.

Cheap baseline:

- `Qwen2.5-VL-7B-Instruct`
  - Good first-pass model.
  - May fail more often on reflections and subtle visual distinctions.

Suggested runtime strategy:

```text
7B or 32B model first
  -> if low confidence / disagreement / reflection-like scene
  -> escalate to 235B
```

## Provider Discussion

Do not hard-code Alibaba Cloud.

Use an OpenAI-compatible provider abstraction:

```env
VLM_BASE_URL=
VLM_API_KEY=
VLM_MODEL=
```

This keeps the code provider-agnostic and makes it easy to test:

- OpenRouter
- PaiAPI
- ZvenoAI
- VEGA API
- AfonAI
- Alibaba DashScope
- other OpenAI-compatible providers

For providers friendly to Russia / ruble payments, candidates found:

- PaiAPI: OpenAI-compatible, says it works from Russia, payment in RUB, card/SBP, claims Vision support.
- ZvenoAI: OpenAI-compatible, payment in RUB, Russian-friendly.
- VEGA API: Russian OpenRouter-like gateway, OpenAI-compatible.
- AfonAI: Russian-language aggregator, OpenAI-compatible.

OpenRouter remains a useful fallback because it has Qwen VL models and crypto credit top-up.

## Vehicle Recognition / RAG Architecture

Saved in:

```text
docs/vehicle-recognition-rag-architecture.md
```

Main idea:

```text
User car photo
  -> Qwen VLM produces make/model/generation hypotheses
  -> Wheel Size API retrieves fitment data and reference images
  -> Qwen VLM reranks candidates using references
  -> backend uses final vehicle identity + fitment data
```

Important conclusion:

- Fine-tuned classifier is better for narrow known catalogues.
- Qwen VLM + Wheel Size API RAG is better for broad coverage and long-tail vehicle recognition.
- Long-term hybrid is best.

## Wheel Size API Notes

Wheel Size / Wheel Fitment API is not primarily a photo recognition API.

It provides:

- vehicle identity;
- generation and trim metadata;
- OE and aftermarket tire/wheel fitment;
- region-aware fitment differences;
- hosted vehicle reference images.

Docs indicated vehicle images are available as hosted URLs for visual confirmation.

## Next Recommended Engineering Step

Create a provider-agnostic VLM smoke-test script:

```text
scripts/vlm_mask_filter_probe.py
```

Inputs:

- original image path;
- Roboflow candidate JSON;
- overlay image path;
- provider config from `.env`.

Outputs:

- `keep_candidate_ids`;
- `reject_candidate_ids`;
- confidence;
- short reasoning summary;
- final combined mask.

Suggested `.env.example` additions:

```env
VLM_BASE_URL=
VLM_API_KEY=
VLM_MODEL=
```

Then run the same test against multiple providers/models and compare:

- Qwen2.5-VL-7B-Instruct
- Qwen2.5-VL-32B-Instruct
- Qwen3-VL-235B-A22B-Instruct

## Verification Already Done

- `ruff check scripts/roboflow_probe.py scripts/roboflow_benchmark.py`: passed.
- `ruff format --check scripts/roboflow_probe.py scripts/roboflow_benchmark.py`: passed.
- Roboflow benchmark on `webapp/cover.jpg` was run successfully with network permission.

## Notes

- `.env` contains local secrets and must not be committed.
- `.DS_Store` is currently untracked in the stage2 worktree.
- `tmp/` is ignored and contains generated benchmark artifacts.
