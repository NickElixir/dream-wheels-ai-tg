# AI Rendering Pipeline

> Part of **Project Dual Track**. This document describes the Rendering Pipeline only; it does not determine technical compatibility. See `docs/fitment-compatibility.md` for the independent Fitment Pipeline and `docs/product-roadmap.md` for the shared delivery plan.

## Scope

This document describes the target production path for virtual wheel fitting. Evaluation scripts and provider experiments are not the production path; they feed provider selection, prompt/mask strategy and quality thresholds.

The Rendering Pipeline answers one question: **“How will these wheels look on this car?”** It may consume confirmed vehicle or rim data where that improves the visual result, but it must not issue a technical compatibility verdict.

## Pipeline

```text
Upload
  → technical validation
  → input quality assessment
  → vehicle/wheel understanding
  → rim understanding
  → render plan
  → generation provider
  → post-generation validation
  → durable result, history and feedback
```

## Inputs

Required:

- car image;
- rim image.

Optional structured rim data, ordered by trust:

1. owned catalog or verified partner feed;
2. user-entered SKU/article and product URL;
3. user-entered specifications;
4. OCR from packaging/marking;
5. VLM extraction from photo;
6. unknown.

The visual image remains required even when structured data is supplied: it is needed for visual appearance and result validation.

## Stage A — technical validation

Validate MIME type, decodability, size, dimensions, EXIF orientation and duplicate content. Reject only unsafe/corrupt inputs.

## Stage B — soft input quality assessment

Initial implementation produces warnings, not hard rejection.

- Cheap CV: blur, brightness, contrast, resolution, extreme crop.
- Semantic checks: car present, wheels visible, rim present, front face sufficiently visible.

Persist `quality_metadata` with model/version and confidence. This creates evidence before enforcing any gate.

## Stage C — vehicle and wheel understanding

Target artifacts:

- vehicle bounding box/mask;
- per-wheel location, visible fraction and occlusion score;
- wheel ellipse/plane estimate when reliable;
- camera-angle classification.

These artifacts improve controlled editing and make failures explainable. They are not required for the first WebApp release.

## Stage D — rim understanding

### Semantic description

Produce normalized attributes such as style, spoke count, primary color, finish, brand/model when available and confidence/source.

### Visual features

- rim segmentation to isolate the object from background;
- front-face crop;
- color/symmetry/shape descriptors;
- visual embedding.

Embeddings are used to find similar catalog products, detect duplicates and compare the generated wheel crop to the reference. They do not perform the image edit themselves.

## Stage E — render plan

Do not construct provider prompts in route handlers. A `RenderPlan` should contain:

- target wheels;
- masks/control artifacts;
- normalized rim data;
- prompt and version;
- provider-neutral generation mode;
- expected wheel count/style;
- pipeline and quality-policy versions.

## Stage F — provider adapter

Use a provider-neutral interface. A provider receives a render plan and returns result location, request identifier, latency, estimated cost and raw response reference.

The initial production path may use one provider. Add fallback only after benchmark evidence supports it.

## Stage G — post-generation validation

Validate independently from the provider:

- vehicle preservation;
- wheel position/count;
- rim similarity to source;
- obvious artifacts around arches, tyres and brakes.

Use geometry checks, VLM judgement and embedding similarity where applicable. A failed validation may trigger one internal retry with an adjusted plan. Never bill this retry separately.

## Evaluation boundary

Evaluation code must support reproducible runs over a versioned case set. Store case inputs, plan/prompt versions, provider output, labels, scores, cost and latency. Do not import evaluation scripts into request handlers.
