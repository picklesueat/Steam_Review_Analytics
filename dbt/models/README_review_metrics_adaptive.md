# Game Review Metrics (Adaptive Decay)

This model produces per–Steam app review metrics that balance lifetime quality, current sentiment,
popularity momentum, and a niche “cult” indicator—while adapting recency decay to each app’s age.

**Model:** `fct_steam_review_metrics_adaptive`  
**Source:** `steam_reviews_enriched` (filtered to non-deleted reviews with non-null `review_created_at`)

## Columns (quick reference)

- **avg_rating** — Lifetime positivity (share of thumbs-up). Range [0,1].
- **edp_current** — Exponentially-Decayed Positivity (current sentiment). Per-app adaptive half-life.
- **decay_ewrr** — Exponentially-Weighted Rate Ratio (short vs long, adaptive). >1 rising popularity; <1 fading.
- **cult_score** — `avg_rating / log(1 + total_reviews)`. Highlights small, beloved titles.
- **half_life_short_days / half_life_long_days / half_life_pos_days** — Effective half-lives used.

## Why these metrics?

- **avg_rating**: clear, stable “overall quality.”  
- **edp_current**: avoids hard cutoffs; reflects sentiment *now*.  
- **decay_ewrr**: smooth popularity momentum without brittle windows.  
- **cult_score**: surfaces hidden gems by softly penalizing sheer volume.

## How the adaptive decay works

Each app’s tenure (days since first review) sets its half-lives:

- `h_short = clamp(0.05 × tenure, 7, 30)`  
- `h_long  = clamp(0.20 × tenure, 30, 180)`  
- `h_pos   = clamp(0.10 × tenure, 30, 120)`

Lambdas are `ln(2)/h`. We cap per-review ages at `weight_age_cap_days` (default 365) to prevent
ancient long tails from over-influencing denominators.

You can tune these via dbt `vars` without touching SQL:
```yaml
vars:
  weight_age_cap_days: 365
  decay_h_short_frac: 0.05
  decay_h_short_min_days: 7
  decay_h_short_max_days: 30
  decay_h_long_frac: 0.20
  decay_h_long_min_days: 30
  decay_h_long_max_days: 180
  pos_half_life_frac: 0.10
  pos_half_life_min_days: 30
  pos_half_life_max_days: 120
  # Optional: anchor calculations to a date for backfills
  # as_of_date: '2025-01-01'
```

## Interpretation tips

- `avg_rating` ~ overall quality.
- `edp_current > avg_rating` ⇒ sentiment improving recently; `< avg_rating` ⇒ softening.
- `decay_ewrr > 1.2` persistently ⇒ momentum is building; `< 0.8` ⇒ momentum is fading.
- `cult_score` is best for discovery; don’t use it alone for global ranking.

## Caveats

- Extremely low-review titles can still be volatile; consider downstream filters like `total_reviews >= 10`.
- `decay_ewrr` is a volume signal, not sentiment—pair with `edp_current`.
- If you need reproducible backfills, set `as_of_date` to a fixed date.

## Maintenance

Owner: Data / Analytics

Upstream schema: `steam_reviews_enriched(app_id, review_created_at, voted_up, helpful_votes, review_updated_at, record_changed_at)`

Refresh cadence: same as `steam_reviews_enriched`.

Tests: see `fct_steam_review_metrics_adaptive.yml`.

## Changelog

- v1.0 — Initial release with adaptive EDP, adaptive EWRR, and cult score.
