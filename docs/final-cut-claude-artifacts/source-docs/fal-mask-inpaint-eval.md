---
geometry: landscape,margin=0.35in
fontsize: 11pt
header-includes:
  - \usepackage{graphicx}
---

# Silver Wheel Replacement: Corrected Eval

## Short Answer

**For the corrected silver-wheel test, Reve production is the best visual result
right now.**

Flux was useful as a strict masked inpaint control, but it is not the visual
winner here: it darkens the silver rim, especially on `C2` and `N2`. The first
corrected comparison makes this obvious: Reve copies the target silver wheel
more directly.

What changed from the previous report:

- Removed Qwen generation examples. The current `fal-ai/qwen-image-edit/inpaint`
  path does not receive the wheel reference image, so it is not relevant for
  "copy this exact wheel".
- Removed the old wide model matrix from the main story. It mixed a flawed
  matte-black prompt with a silver reference image.
- Added the original wheels for `C1`, `C2`, and `N2`, so it is clear what was
  replaced.
- Added a clean Reve production vs Reve masked eval comparison.
- Left a clear slot for the next experiment: **OpenAI GPT Image**.

Current demo recommendation:

1. Show **Reve production** as the best result for tomorrow's stakeholder demo.
2. Keep **Reve masked eval** as a controlled experiment, not the production
   path.
3. Keep **Flux** as the strict-mask baseline, not as the visual winner.
4. Add **OpenAI GPT Image** next using the same three-case layout.

\newpage

## Inputs

All corrected runs use the same target wheel: the silver multi-spoke rim below.
The left side shows the original wheels on each source car.

\begin{center}
\includegraphics[width=\textwidth,height=0.68\textheight,keepaspectratio]{docs/assets/fal-mask-inpaint-eval/presentation/input-wheels-and-target.jpg}
\end{center}

Corrected prompt principle:

```text
Use the exact wheel design, color, finish, spoke pattern, center cap, and material from the reference image.
Preserve original scene lighting.
Do not alter car body, color, or background.
```

Important: the old prompt said `matte black` while the reference image was
silver. That earlier visual report is useful only as a record of what happened,
not as a fair silver-wheel comparison.

\newpage

## Reve Production vs Reve Masked Eval

This is the key Reve comparison.

- **Reve production** receives `car + wheel reference`, no mask. This matches the
  current production request shape.
- **Reve masked eval** receives `car + wheel reference + mask`. This is an eval
  experiment, not the current production path.

\begin{center}
\includegraphics[width=\textwidth,height=0.78\textheight,keepaspectratio]{docs/assets/fal-mask-inpaint-eval/presentation/reve-production-vs-masked.jpg}
\end{center}

\newpage

\begin{center}
\includegraphics[width=\textwidth,height=0.94\textheight,keepaspectratio]{docs/assets/fal-mask-inpaint-eval/presentation/ivan-C1-case-card.jpg}
\end{center}

\newpage

\begin{center}
\includegraphics[width=\textwidth,height=0.94\textheight,keepaspectratio]{docs/assets/fal-mask-inpaint-eval/presentation/ivan-C2-case-card.jpg}
\end{center}

\newpage

\begin{center}
\includegraphics[width=\textwidth,height=0.94\textheight,keepaspectratio]{docs/assets/fal-mask-inpaint-eval/presentation/ivan-N2-case-card.jpg}
\end{center}

\newpage

## Model Status

Case takeaways:

- `C1`: **Reve production wins visually.** Reve masked eval is close. Flux keeps
  the edit localized but makes the target darker and less faithful.
- `C2`: **Reve production is the cleanest result.** Reve masked eval is usable
  but less clean. Flux loses the silver wheel identity.
- `N2`: **Reve production is still the best demo candidate.** It keeps the wheel
  silver and readable in low light. Flux collapses too far toward a dark rim.

| Path | Gets car | Gets wheel reference | Gets mask | Use in this report |
| --- | ---: | ---: | ---: | --- |
| Reve production | yes | yes | no | Main visual winner |
| Reve masked eval | yes | yes | yes | Side-by-side control |
| Flux Kontext inpaint | yes | yes | yes | Strict-mask baseline |
| Qwen current fal inpaint | yes | no | yes | Excluded |
| OpenAI GPT Image via official API | planned | planned | planned | Ready to run with `OPENAI_API_KEY` |
| OpenAI GPT Image via AITUNNEL | yes | partial | partial | Blocked for honest masked reference test |

Why Qwen is out:

The current Qwen fal config receives only `image_url`, `mask_url`, and `prompt`.
It does not receive the wheel reference image. That means it cannot honestly
copy this exact silver rim.

Why Flux is not the winner:

Flux is better when the goal is "edit only inside this mask". But the demo goal
is "make the car look like it has this exact silver target wheel". On the
corrected examples, Reve production does that more clearly.

\newpage

## Next: OpenAI GPT Image

Add OpenAI GPT Image as the next row in the same layout:

```text
source car + target wheel reference + alpha mask
```

Do not change the cases, prompt intent, or visual layout. The next comparison
should answer only one question:

> Does OpenAI GPT Image beat Reve production on the same silver wheel target?

Suggested first run:

- `C1`, `C2`, `N2`
- same corrected target rim
- same adapted prompt
- medium quality first
- one high-quality retry only if the medium result is close

If GPT Image wins, it becomes the new demo candidate. If not, keep Reve
production as the current best visual path.

AITUNNEL implementation status:

- The local runner now supports OpenAI-compatible AITUNNEL via
  `AITUNNEL_API_KEY` and `AITUNNEL_BASE_URL`.
- AITUNNEL `/v1/images/generations` works with `gpt-image-2`.
- AITUNNEL `/v1/images/edits` works for `image + mask` when the source image is
  sent as PNG.
- AITUNNEL `/v1/images/edits` also works for multiple `image[]` inputs without
  a mask.
- The required honest test shape, `image[] + mask`, currently fails through
  AITUNNEL before returning a JSON API error. Mixing `image` and `image[]`
  returns a normal 400 parameter error.

Conclusion: use the official OpenAI API for the controlled
`car + wheel reference + alpha mask` GPT Image row, or ask AITUNNEL support to
enable/fix `image[] + mask` passthrough for GPT Image edits.

## Run References

- Manifest: `tmp/fal-inpaint-eval/ivan-corrected-silver-3cases.jsonl`
- Reve production outputs: `tmp/reve-image-edit-eval/results-corrected-silver-production`
- Reve masked eval outputs: `tmp/reve-image-edit-eval/results-corrected-silver-masked`
- Flux masked baseline outputs: `tmp/fal-inpaint-eval/results-corrected-silver-flux`
- OpenAI/AITUNNEL runner: `scripts/openai_image_edit_eval.py`
- Presentation assets: `docs/assets/fal-mask-inpaint-eval/presentation`
