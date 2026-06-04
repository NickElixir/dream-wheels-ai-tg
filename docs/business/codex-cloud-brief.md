# Dream Wheels AI — Codex Cloud Business Brief

## Objective

Prepare B2C business strategy, unit economics, June pricing, and marketing plan
for Dream Wheels AI.

This brief is intentionally public-safe: it must not contain personal seller
details, tax IDs, API keys, database URLs, Robokassa passwords, bot tokens, or
private financial credentials.

## Product Summary

Dream Wheels AI is a Telegram Mini App for AI wheel visualization.

User flow:

1. User opens the Telegram Mini App.
2. User uploads a side-view car photo.
3. User uploads a front-view wheel photo.
4. Backend creates a render job.
5. Worker sends images to the external image generation API.
6. User receives a photorealistic image of their own car with selected wheels.

Core user value:

> See wheels on your own car before buying them.

## Current Product State

- B2C Telegram Mini App exists.
- Car/wheel upload flow exists.
- Backend: FastAPI, Postgres, Redis queue, external image generation API.
- Results are saved and returned to the user.
- Robokassa preorder payment backend has been implemented on a staging branch.
- Legal/moderation requirements were identified: offer, privacy policy, refund
  policy, seller details, contacts, service description, payment terms.

## Current Technical Context

Primary docs to read:

- `README.md`
- `docs/architecture.md`
- `docs/dream_wheels_ai_architecture_v1_2.md`
- `webapp/README.md`
- `webapp/app.js`
- `webapp/index.html`
- `webapp/style.css`

Payment staging branch for implementation context:

- `staging/robokassa-payments`

Main payment assumptions:

- Payment provider: Robokassa.
- User enters email for receipt.
- Backend creates a local preorder.
- Backend returns a signed Robokassa checkout URL.
- Robokassa calls backend ResultURL after payment.
- Backend verifies signature and amount, then marks preorder as paid.
- NPD receipt is expected through Robokassa/RoboReceipts SMZ.

## Scope

In scope:

- B2C Telegram Mini App.
- Credits/packages/subscription policy.
- Free trial policy.
- Founder Pass / June launch offer.
- Unit economics.
- June marketing campaign.
- UX state map for payment, credits, generation, failed generation, receipts.
- Backend/frontend requirements derived from the business model.

Out of scope:

- B2B website.
- B2B widget.
- Dealer integrations.
- White-label flows.
- Sales CRM for shops.

## Open Product Decisions

Decide and justify:

1. Whether to offer a free trial.
2. Whether the core paid unit is render credits, time-limited access, or both.
3. Whether a June Founder Pass should exist.
4. Whether "unlimited for one month" is viable, and what fair-use cap is needed.
5. When render credits are deducted.
6. When failed renders return credits.
7. How to define refund rules.
8. How long purchased credits remain valid.
9. Which packages should be shown in checkout.
10. Which states must appear in the Mini App cabinet.

## Candidate Offers

Initial hypotheses only. These are not final.

| Offer | Hypothesis |
| --- | --- |
| Free Trial | 1 free render per Telegram user, possibly with watermark or slow queue |
| Start | Small paid package for users choosing wheels now |
| Pro | Better value package for users testing multiple wheel styles |
| Master | Large package for enthusiasts / repeated experiments |
| Founder June Pass | Limited June launch offer to collect first prepayments |
| Unlimited Month | Original aggressive idea; needs hard cap/fair-use math |

## Unit Economics Inputs Needed

The model must support editable assumptions:

- API cost per generation attempt.
- Average attempts per successful render.
- Generation failure rate.
- Refund rate.
- Robokassa commission.
- Fixed infrastructure cost.
- Storage cost.
- Support/manual handling buffer.
- Free trial volume.
- Free trial to paid conversion.
- Expected renders per paid user.
- Heavy-user scenario.
- June minimum revenue target.

## Marketing Goal For June

Primary goals:

1. Validate B2C demand.
2. Collect first prepayments.
3. Fund external API usage, hosting, and team work.
4. Learn which offer converts: Free Trial, Start package, Founder Pass, or
   limited monthly access.

Primary target audience:

- Car owners currently choosing wheels.
- Auto enthusiasts doing visual tuning.
- Users in Telegram/VK/Drive2 auto communities.
- Buyers comparing wheel styles before purchase.

Do not focus on B2B in this plan.

## Required Output From Codex Cloud

Produce:

1. Final B2C product pipeline.
2. Unit economics table with formulas and scenario analysis.
3. Recommended June packages and pricing.
4. Free trial policy.
5. Founder Pass policy.
6. Refund and failed-generation credit rules.
7. June marketing campaign plan.
8. UX state map for Mini App payment/credits/generation.
9. Backend/frontend requirement deltas.
10. Risks and decision checklist before launch.
