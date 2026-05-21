# Claude Brief - Dream Wheels AI Final Cut Presentation

## Communication Rules

- Chat with Nikolai in Russian if needed.
- All slide text, titles, labels, charts, diagrams, and speaker-facing slide copy should be in English.
- Make the deck visually clean and readable in 16:9.
- Avoid overloaded academic slides. Use one strong idea per slide.
- This is a final course/project presentation: it should explain the concept, show technical depth, include the latest weekly progress, and end with team insights.

## Desired Tone

Make the project feel practical, product-driven, and visually memorable.
The audience should quickly understand:

- what the product does;
- why wheel-mask quality matters;
- what the team actually built and tested;
- what changed in the last week;
- what lessons are useful for other teams.

Aim for a "wow, this is a real product pipeline" feeling, not just a model report.

## Core Product Story

Dream Wheels AI lets a user upload:

1. a photo of their car;
2. a photo of a wheel/rim.

The system returns an AI-remixed image showing how the car could look with the new wheels.

Current product shape:

- Telegram bot user flow;
- FastAPI backend;
- Redis queue/session/rate-limit;
- Supabase/Postgres/Storage;
- Render deployment;
- Reve API image remix;
- ongoing experiments with masked image editing and VLM-based quality control.

Use `source-docs/product-readme.md` and `source-docs/architecture.md` for details.

## Recommended Deck Structure

### 1. Opening - Product Concept

Slide idea:

**Dream Wheels AI: Try New Wheels On Your Own Car**

Visual:

- Big car/wheel transformation image if available.
- Or use `assets/fal-mask-inpaint-eval/input-wheels-and-target.jpg` as a collage of source cars and target wheel.

Message:

```text
Users should not have to imagine whether a wheel style fits their car.
They should see it on their own photo before buying or customizing.
```

### 2. Why This Is Hard

Slide title:

**The Hard Part Is Not Just Generation**

Visual:

- Use examples from `assets/wheel-candidate-manual/`.
- Show valid wheel vs reflection/headlight/rain reflection.

Message:

```text
Wheel-like regions appear in reflections, shadows, headlights, body panels,
background cars, and generated artifacts.
Bad candidates increase cost and can ruin the final image.
```

### 3. Product Pipeline

Slide title:

**From User Photo To Generated Result**

Visual:

- Use a simplified pipeline diagram based on `source-docs/architecture.md`.

Suggested flow:

```text
Telegram / WebApp
  -> FastAPI job API
  -> Redis queue
  -> Worker
  -> Storage + database
  -> image generation model
  -> result back to user
```

### 4. Stage 2 VLM Mask Filter

Slide title:

**Stage 2: VLM Filters Wheel Candidates Before Generation**

Use the prepared image:

- `assets/stage2-vlm-filter/stage2-vlm-filter-pipeline.png`

Message:

```text
Roboflow/YOLO proposes wheel candidates.
A VLM sees the original image, labeled candidate overlay, and metadata.
It keeps only physical wheels and rejects reflections/artifacts.
```

### 5. Key Experiment

Slide title:

**VLM Filtering Kept Real Wheels And Rejected Reflections**

Use:

- `assets/stage2-vlm-filter/cover-original.jpg`
- `assets/stage2-vlm-filter/cover-qwen3-30b-candidates-overlay.png`
- `assets/stage2-vlm-filter/cover-qwen3-30b-final-mask.png`
- optional failure: `assets/stage2-vlm-filter/cover-qwen25-72b-failure-mask.png`

Key numbers:

| Model | Keep IDs | Reject IDs | Result |
|---|---:|---:|---|
| Qwen3-VL-235B | `[0, 3]` | `[1, 2]` | Correct |
| Qwen3-VL-30B | `[0, 3]` | `[1, 2]` | Correct |
| Qwen2.5-VL-72B | `[0]` | `[1, 2, 3]` | Failed rear wheel |

Important insight:

```text
Do not send only the top-2 largest candidates to Stage 2.
The small rear wheel can be removed before the VLM ever sees it.
```

### 6. Dataset And Evaluation Plan

Slide title:

**Quality Needs Hard Negatives, Not Just Clean Cars**

Use:

- `source-docs/stage2-hard-negative-dataset-requirements.md`
- `source-docs/wheel-candidate-annotator-manual.md`

Visual:

- A 7-bucket dataset plan.

Suggested buckets:

- wet road / water reflections;
- glossy showroom reflections;
- night / low-light / neon glare;
- wheel-shaped shadows;
- background vehicles;
- cropped / occluded wheels;
- clean ordinary car photos.

### 7. Latest Week Update - Corrected Generation Eval

Slide title:

**Latest Update: Corrected Silver-Wheel Generation Eval**

Use:

- `source-docs/fal-mask-inpaint-eval.md`
- `assets/fal-mask-inpaint-eval/reve-production-vs-masked.jpg`
- `assets/fal-mask-inpaint-eval/ivan-C1-case-card.jpg`
- `assets/fal-mask-inpaint-eval/ivan-C2-case-card.jpg`
- `assets/fal-mask-inpaint-eval/ivan-N2-case-card.jpg`

Main message:

```text
For the corrected silver-wheel test, Reve production is the best visual result right now.
Flux is useful as a strict masked baseline, but it darkens the target wheel.
Qwen current fal inpaint was excluded because it does not receive the wheel reference image.
OpenAI GPT Image is the next honest comparison.
```

### 8. Future Layer - Final-Image VLM QA

Slide title:

**Future Layer: Final-Image VLM Quality Gate**

Use:

- `latest-week/final-image-vlm-qa-slide-note.md`
- optional external image references in `external-references/suggested-internet-visuals.md`
- colleague notebook in `latest-week/validation_vlm_colleague_notebook.ipynb`

Message:

```text
After generation, a VLM can review the final image and route it to:
accept, manual review, or reject.
```

Do not present the notebook as a validated benchmark. Present it as a useful prototype idea.

### 9. Product / Business Direction

Slide title:

**Where This Can Create Value**

Use:

- `source-docs/stakeholder-analysis-partnership-outreach.md`

Segments:

- custom wheel manufacturers;
- tuning and styling studios;
- wheel and tire retailers;
- private sellers and marketplace listings.

Core value:

```text
Reduce the imagination gap before a wheel purchase or customization decision.
```

### 10. Team Insights And Course Learnings

Slide title:

**What We Learned Building A Product-Scoped DL System**

Use:

- `team-course-insights/team-course-insights-and-audience-recommendations.md`

Keep this human and practical.

### 11. Recommendations To Audience

Slide title:

**Recommendations For Applied AI Projects**

Suggested message:

```text
Start with the product failure mode.
Build the smallest benchmark that can expose it.
Keep humans in the loop for ambiguous visual quality.
Measure latency, cost, and failure recovery, not only model accuracy.
Treat prompts, masks, and datasets as product infrastructure.
```

### 12. Closing

Slide title:

**From Demo To Reliable Product**

Closing line:

```text
The path from an impressive AI demo to a usable product is quality control:
better candidates, better masks, better evaluation, and better feedback loops.
```

## Visual Direction

Use these visual patterns:

- full-width before/after image rows;
- candidate overlays with ID labels;
- compact scorecards;
- one pipeline diagram with strong visual hierarchy;
- small "lesson learned" callouts;
- accept / review / reject decision strips;
- no dense paragraph slides.

Potential wow moments:

- reveal the reflection failure: original -> candidate overlay -> VLM final mask;
- show Qwen2.5 failure next to Qwen3 success;
- show corrected generation case cards;
- end with a practical "applied AI checklist" that feels useful to the audience.

## Things To Avoid

- Do not claim Stage 2 is production-proven yet.
- Do not present the colleague notebook as an evaluated benchmark.
- Do not overstate exact fitment validation: VLM can judge visual plausibility, not bolt pattern, offset, center bore, or exact rim diameter.
- Do not mix old matte-black prompt results with the corrected silver-wheel story.
- Do not bury the audience in architecture details. Use architecture only to show this is a real product.
