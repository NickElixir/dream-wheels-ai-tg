# Team Insights And Audience Recommendations

Use this as source material for the final 2-3 slides of the presentation.

## Slide: What We Learned

Suggested title:

**What We Learned Building A Product-Scoped DL System**

Suggested slide copy:

```text
The hardest part was not choosing the biggest model.
It was defining the right failure mode, building the right visual evidence,
and keeping the pipeline useful for a real user.
```

Key insights:

- Product quality depends on the weakest visual step: candidate detection, mask selection, prompt alignment, or final image QA.
- A visually impressive generation can still fail the product if the wheels are unrealistic, mismatched, or placed badly.
- Small pipeline decisions matter: top-2 candidate truncation removed a real rear wheel before the VLM could evaluate it.
- Bigger models are not automatically better: Qwen3-VL-30B solved the reflection case that Qwen2.5-VL-72B failed.
- Evaluation examples must match real failure modes, not only clean benchmark images.
- Human review is not a fallback weakness; it is how ambiguous visual quality becomes a reliable dataset.

## Slide: Course Project Insights

Suggested title:

**From Model Experiment To Product Loop**

Suggested visual:

```text
Failure mode
   -> dataset / examples
   -> model or VLM decision
   -> visual artifact
   -> human review
   -> improved benchmark
```

Suggested slide copy:

```text
Applied deep learning work became clearer when we stopped asking
"which model is best?" and started asking
"which product failure are we trying to prevent?"
```

Possible speaker notes:

- The course gave us the technical vocabulary for classification, segmentation, transfer learning, and evaluation.
- The product forced us to care about deployment constraints: latency, API cost, routing, false rejection, and user trust.
- The most valuable experiments were the ones with visual artifacts that stakeholders could understand immediately.

## Slide: Recommendations For Applied AI Teams

Suggested title:

**Recommendations For Applied AI Projects**

Suggested slide copy:

```text
1. Start from the product failure mode.
2. Build the smallest benchmark that exposes it.
3. Keep visual evidence next to every metric.
4. Tune for asymmetric errors, not generic accuracy.
5. Treat prompts, masks, and datasets as product infrastructure.
6. Add human review where judgment is subjective.
7. Measure cost and latency before calling something production-ready.
```

## Slide: What Comes Next

Suggested title:

**Next Steps Toward A Reliable Product**

Suggested slide copy:

```text
Short term:
• run OpenAI GPT Image on the corrected silver-wheel eval
• collect 50 hard-negative images for Stage 2
• add final-image VLM QA as a review router

Medium term:
• build a lightweight wheel-candidate classifier
• track candidate-level review labels
• evaluate cost, latency, and failure recovery
• pilot with tuning studios or custom wheel makers
```

## Closing Line

```text
The path from an impressive AI demo to a reliable product is quality control:
better candidates, better masks, better evaluation, and better feedback loops.
```
