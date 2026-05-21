# Dream Wheels AI - Final Cut Presentation Artifacts

Date: 2026-05-21

This folder is a curated artifact bundle for preparing the Final Cut presentation.
It is meant to be passed to Claude or another presentation-building agent.

## Start Here

Read these files first:

1. `CLAUDE_FINAL_CUT_BRIEF.md` - presentation storyline, slide structure, visual direction, and what to emphasize.
2. `source-docs/product-readme.md` - product, stack, backend architecture, current production flow.
3. `source-docs/ai-quality-stage2-vlm-filter-experiment.md` - main Stage 2 VLM filter result.
4. `source-docs/fal-mask-inpaint-eval.md` - latest-week corrected image-generation eval.
5. `team-course-insights/team-course-insights-and-audience-recommendations.md` - ending section for course/team insights.

## Folder Map

| Folder | Purpose |
|---|---|
| `source-docs/` | Main source documents copied from the project repo. |
| `assets/stage2-vlm-filter/` | Visuals for the Stage 2 mask-filter story. |
| `assets/fal-mask-inpaint-eval/` | Slide-ready visual comparisons for the latest image-generation eval. |
| `assets/wheel-candidate-manual/` | Annotation examples: valid wheel, reflections, invalid objects. |
| `latest-week/` | Colleague notebook and short notes about recent possible QA additions. |
| `team-course-insights/` | Suggested closing slides about team learnings and recommendations. |
| `external-references/` | Suggested internet images and links for optional visuals. |

## High-Level Presentation Goal

The presentation should tell one coherent story:

```text
We started with a real product idea:
AI wheel try-on from a user's own car photo.

We built and evaluated the quality-critical parts:
candidate detection, VLM filtering, mask quality, and image-generation choices.

This week we refined the visual generation comparison and identified a future
final-image VLM QA layer.

The project gave practical lessons about product-scoped deep learning:
data quality, evaluation design, model choice, latency, cost, and human review.
```

The deck should be visual-first. Prefer diagrams, before/after comparisons,
candidate overlays, and compact metrics over long paragraphs.

## Source Document Priority

Use these as primary sources:

- `source-docs/product-readme.md`
- `source-docs/architecture.md`
- `source-docs/ai-quality-stage2-vlm-filter-experiment.md`
- `source-docs/fal-mask-inpaint-eval.md`
- `source-docs/stage2-hard-negative-dataset-requirements.md`
- `source-docs/stakeholder-analysis-partnership-outreach.md`
- `team-course-insights/team-course-insights-and-audience-recommendations.md`

Use these only as supporting context:

- `source-docs/wheel-candidate-filtering-project-proposal.md`
- `source-docs/wheel-candidate-annotator-manual.md`
- `source-docs/wheel-mask-segmentation-handoff.md`
- `source-docs/vehicle-recognition-rag-architecture.md`
- `source-docs/keep-alive-setup.md`
- `source-docs/*CHAT_HANDOFF*.md`
