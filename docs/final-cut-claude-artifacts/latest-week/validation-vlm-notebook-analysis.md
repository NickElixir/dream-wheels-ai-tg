# Colleague Notebook Analysis - `validation_vlm.ipynb`

## What The Notebook Does

The notebook is a Colab prototype for evaluating final generated car images with an OpenAI VLM.

It uploads image files, sends each image to `gpt-4.1-mini`, and asks the model to return JSON scores for:

- visual attractiveness;
- style consistency;
- physical realism;
- approximate fitment plausibility;
- detected problems;
- overall score;
- decision: `accept`, `needs_review`, or `reject`.

## How It Relates To The Project

This is not the same as the Stage 2 VLM mask filter.

| Current Stage 2 VLM Filter | Colleague Notebook |
|---|---|
| Runs before generation. | Runs after generation. |
| Selects candidate mask IDs. | Scores the final rendered image. |
| Solves reflection/artifact leakage in masks. | Solves final result QA and review routing. |
| Produces a final mask. | Produces JSON quality scores. |

## Presentation Recommendation

Use the idea, not the notebook results.

Recommended framing:

```text
Optional future QA layer:
after generation, a VLM reviews the final image for visual realism,
style consistency, artifacts, and approximate fitment plausibility.
```

Do not present it as a validated benchmark because:

- no saved VLM result table is present in the notebook;
- only one uploaded screenshot is visible in saved outputs;
- there is no manual-review comparison;
- there are no aggregate metrics;
- the implementation is a manual Colab prototype.

## Why Requests May Be Slow In Colab

Likely reasons:

- images are sent as full base64 payloads without resize/compression;
- requests run sequentially, one image at a time;
- PNG screenshots can be large;
- the MIME label is always `image/jpeg`, even for PNG files;
- no async or concurrent batching;
- no partial CSV checkpoint after each image.

## If This Becomes A Real Component

Improve it by adding:

- image resizing before upload;
- correct MIME type detection;
- strict JSON schema validation;
- retry/backoff;
- per-image checkpointing;
- batch summary metrics;
- manual review labels for a small evaluation set;
- latency and cost logging.
