# Unit Economics Template

Use this as the baseline model for Dream Wheels AI B2C pricing.

## Assumptions

| Input | Symbol | Value | Notes |
| --- | --- | ---: | --- |
| API cost per generation attempt | `api_cost_attempt` | TBD | External image generation cost |
| Attempts per successful render | `attempts_success` | TBD | Include retries/regeneration |
| Generation failure rate | `failure_rate` | TBD | Jobs that do not deliver a usable result |
| Robokassa commission rate | `payment_fee_rate` | TBD | Percent of gross payment |
| Robokassa fixed fee | `payment_fee_fixed` | TBD | If applicable |
| Monthly fixed infra cost | `infra_monthly` | TBD | Render/Supabase/Redis/etc. |
| Expected paid renders/month | `paid_renders_month` | TBD | Used to allocate fixed costs |
| Support/refund buffer per render | `support_buffer` | TBD | Manual handling + refunds |
| Free trial renders/month | `free_renders_month` | TBD | Launch subsidy |
| Free trial conversion | `free_to_paid_conversion` | TBD | Trial users to paid users |

## Core Formulas

```text
api_cost_success = api_cost_attempt * attempts_success

infra_cost_render = infra_monthly / max(paid_renders_month, 1)

cogs_per_success =
  api_cost_success
  + infra_cost_render
  + support_buffer

payment_fee =
  package_price * payment_fee_rate
  + payment_fee_fixed

package_cogs =
  included_renders * cogs_per_success

contribution_margin =
  package_price
  - payment_fee
  - package_cogs

gross_margin_percent =
  contribution_margin / package_price
```

## Package Scenarios

| Package | Price RUB | Included renders | Revenue after fee | COGS | Contribution margin | Margin % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Free Trial | 0 | 1 | 0 | TBD | TBD | N/A |
| Start | TBD | TBD | TBD | TBD | TBD | TBD |
| Pro | TBD | TBD | TBD | TBD | TBD | TBD |
| Master | TBD | TBD | TBD | TBD | TBD | TBD |
| Founder June Pass | TBD | TBD | TBD | TBD | TBD | TBD |
| Unlimited Month | TBD | Fair-use cap TBD | TBD | TBD | TBD | TBD |

## Stress Tests

Model at least these cases:

1. Conservative usage.
2. Expected usage.
3. Heavy-user abuse.
4. High failure rate.
5. Low conversion from free trial.
6. API cost increase.

## Launch Decision Criteria

Do not launch a package if:

- Contribution margin is negative in expected usage.
- Heavy-user scenario can exhaust API budget.
- Refund/credit rules are unclear.
- Legal copy and checkout copy disagree.
- Backend cannot enforce the promised limits.
