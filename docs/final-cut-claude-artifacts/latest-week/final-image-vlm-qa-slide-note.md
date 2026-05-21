# Optional Slide - Final-Image VLM Quality Gate

## Slide Title

Future Layer: Final-Image VLM Quality Gate

## Main Message

After wheel generation, a VLM can review the final image before delivery and route it to **accept**, **manual review**, or **reject**.

## On-Slide Flow

```text
Generated car image
        ↓
Final-image VLM QA
        ↓
Scores:
Style match · Visual realism · Artifacts · Fitment plausibility
        ↓
Accept / Needs review / Reject
```

## Short Body Copy

```text
This layer checks the final rendered result, not the mask.

It can flag:
• unnatural wheel geometry
• style mismatch with the car
• visible generation artifacts
• implausible wheel size or tire thickness
• wheel/body/road intersections
```

## Speaker Notes

Our current Stage 2 work focuses on mask quality: keeping real wheel candidates and rejecting reflections or artifacts before generation.

A complementary next step is post-generation validation. After the image is produced, a VLM can inspect the final result as a user would: does it look realistic, attractive, physically plausible, and consistent with the car?

The colleague's notebook is a useful prototype of this idea, but it is not yet a benchmark. It should be presented as a future QA layer, not as a validated result.

## Suggested Visual

Left side:

- a strong close-up photo of a wheel/rim or a generated car result;
- optional overlay with a subtle "QA scan" effect.

Right side:

- four compact scoring chips:
  - Style Match
  - Realism
  - Artifacts
  - Fitment
- bottom decision strip:
  - ACCEPT
  - NEEDS REVIEW
  - REJECT

Keep it visual and simple. This is a roadmap slide, not a benchmark slide.
