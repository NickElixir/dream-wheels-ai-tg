# Vehicle Recognition and Fitment RAG Architecture

## Goal

Dream Wheels needs to identify the user's vehicle from an uploaded photo well enough to:

- understand make, model, generation, approximate year range, body style, and market when possible;
- retrieve reliable wheel/tire fitment data;
- choose or validate the visible wheel locations and masks used by the rendering pipeline;
- support a broad catalogue of vehicles without training a new classifier for every model upfront.

This document captures the proposed architecture for the next AI quality stage.

## Recommendation

Use a hybrid approach:

1. **VLM first pass**
   - Use a vision-language model, such as Qwen VL, to infer a small candidate set from the user photo.
   - Expected output: structured JSON with make/model/generation/year-range hypotheses and confidence.

2. **Wheel Size API retrieval**
   - Query Wheel Size / Wheel Fitment API using the VLM hypotheses.
   - Retrieve vehicle identity, generation metadata, trim/region data, fitment records, and hosted reference images.

3. **VLM reranking with references**
   - Send the user image plus reference images and structured candidate metadata back to the VLM.
   - Ask the VLM to select the best candidate, reject weak matches, and explain which visual signals mattered.

4. **Wheel mask pipeline**
   - Use `wheels-tires-body/1` or a future local segmentation model to generate wheel candidates.
   - Use simple geometric filters first.
   - Later, optionally use the VLM as a candidate selector to reject reflections, shadows, and non-wheel artifacts.

5. **Fitment lookup and render preparation**
   - Once vehicle identity is selected, use fitment data to guide compatible wheel sizes and rendering constraints.

## Why Not Only a Fine-Tuned Classifier?

A fine-tuned image classifier can be the most accurate option when the class list is narrow and well represented in the training data.

It is a good long-term optimization for:

- high-volume vehicles;
- known target markets;
- repeated user traffic;
- low-latency and low-cost inference.

However, it has important limitations:

- every make/model/generation class needs labeled training data;
- new vehicles and rare regional variants require retraining;
- trim, facelift, market, and generation boundaries are often subtle;
- long-tail coverage becomes expensive to maintain.

## Why VLM + RAG Helps

RAG does not magically make a VLM know every vehicle. It gives the VLM relevant external context at inference time.

The useful loop is:

```text
User photo
  -> VLM produces candidate vehicle identities
  -> Wheel Size API retrieves structured metadata and reference images
  -> VLM compares user photo against references
  -> final ranked candidate with confidence
```

This improves cases where the model can identify the family but not the generation, facelift, or market-specific variant.

The reference images are especially useful for visual comparison of:

- headlights and taillights;
- grille and bumper shape;
- side silhouette;
- window line;
- wheel arch geometry;
- body style and door count.

## Wheel Size API Role

Wheel Size / Wheel Fitment API is not primarily a photo recognition API. It is a structured fitment database.

Its value here is:

- make/model/year/generation/trim metadata;
- OE and aftermarket tire/wheel fitment data;
- region-aware fitment differences;
- hosted reference images for vehicle generations;
- validation of user-selected or VLM-detected vehicle identity.

The API documentation indicates that vehicle images are available as hosted URLs for visual confirmation. Configurator imagery can come from EVOX images and manually added images.

## Expected Accuracy

### Highest accuracy for a narrow known catalogue

Use a fine-tuned classifier or detector.

This is best when:

- the supported vehicle list is fixed;
- the dataset is large and well labeled;
- generation/trim labels are available;
- inference cost and latency matter more than broad coverage.

### Highest coverage across many vehicles

Use Qwen VLM + Wheel Size API RAG.

This is best when:

- the catalogue is broad;
- many models are rare or region-specific;
- new vehicles should work without retraining;
- the product can tolerate a confidence/reranking step.

## Proposed MVP Flow

```text
1. User uploads car image.
2. Qwen VL returns top vehicle hypotheses:
   [
     { "make": "Toyota", "model": "Prius", "generation": "XW30", "years": "2009-2015", "confidence": 0.72 },
     ...
   ]
3. Backend queries Wheel Size API for candidates and reference images.
4. Qwen VL reranks:
   {
     "selected_candidate_id": "...",
     "confidence": 0.86,
     "reasoning_summary": "Headlight shape and side window line match XW30 generation.",
     "needs_user_confirmation": false
   }
5. Backend retrieves fitment data for the selected candidate.
6. Wheel segmentation generates visible wheel masks.
7. Renderer receives vehicle identity, fitment constraints, wheel masks, and user wheel image.
```

## VLM Candidate Selection for Wheel Masks

The same VLM can help reject false wheel masks.

Example:

```text
Input:
- original image
- overlay image with candidate masks labeled 0..N
- JSON candidate metadata: class, confidence, bbox, area, center

Output:
{
  "keep_candidate_ids": [0, 2],
  "reject_candidate_ids": [1, 3],
  "reasoning_summary": "Candidate 3 is a road reflection, not a physical wheel."
}
```

This should be used as a second-stage filter after cheap geometric rules.

## Data to Log for Future Fine-Tuning

Every user flow should eventually save:

- original uploaded image;
- VLM candidate list;
- selected vehicle identity;
- Wheel Size API candidate IDs;
- reference image IDs used for reranking;
- user confirmation/correction if available;
- wheel mask candidates and selected mask IDs;
- final render success/failure signal.

This data becomes the training set for future local classifiers and segmentation improvements.

## Implementation Notes

- Use `qwen3-vl-flash` first for low-cost experiments.
- Keep prompts JSON-only and deterministic.
- Store VLM confidence and require user confirmation below a threshold.
- Do not rely on VLM alone for exact pixel masks.
- Use segmentation models for masks and VLM for reasoning/reranking.
- Keep Wheel Size API data usage aligned with its terms of service.

## Open Questions

- Which regions should be prioritized first: USDM, EUDM, JDM, global?
- What confidence threshold should trigger user confirmation?
- Should we ask users to confirm make/model before rendering?
- How many reference images are optimal per reranking request?
- Can Wheel Size API candidate images cover enough visual variants for our target markets?
- Should we use an external vehicle recognition API as a baseline benchmark?
