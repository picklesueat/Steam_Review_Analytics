{{ config(materialized='table') }}

{# -----------------------------
    Tunable parameters (dbt vars)
   ----------------------------- #}
{% set weight_age_cap_days     = var('weight_age_cap_days', 365) %}

{% set h_short_frac            = var('decay_h_short_frac', 0.05)  %}
{% set h_short_min_days        = var('decay_h_short_min_days', 7) %}
{% set h_short_max_days        = var('decay_h_short_max_days', 30) %}

{% set h_long_frac             = var('decay_h_long_frac', 0.20)   %}
{% set h_long_min_days         = var('decay_h_long_min_days', 30) %}
{% set h_long_max_days         = var('decay_h_long_max_days', 180) %}

{% set h_pos_frac              = var('pos_half_life_frac', 0.10)  %}
{% set h_pos_min_days          = var('pos_half_life_min_days', 30) %}
{% set h_pos_max_days          = var('pos_half_life_max_days', 120) %}

{# Optional: override "as of" date for backfills (YYYY-MM-DD). Default = CURRENT_DATE #}
{% set as_of_date_override     = var('as_of_date', None) %}

with reviews as (
    select
        app_id,
        recommendationid,
        review_created_at,
        review_updated_at,
        record_changed_at,
        voted_up,
        coalesce(helpful_votes, 0) as helpful_votes
    from {{ ref('steam_reviews_enriched') }}
    where review_created_at is not null
      and coalesce(is_deleted, false) = false
),
app_bounds as (
    select
        app_id,
        min(review_created_at) as first_review_at,
        max(review_created_at) as latest_review_at,
        max(record_changed_at) as record_changed_at,
        max(review_updated_at) as latest_review_updated_at
    from reviews
    group by app_id
),
params as (
    select
        {% if as_of_date_override %}
            date '{{ as_of_date_override }}'::date as as_of_date
        {% else %}
            current_date as as_of_date
        {% endif %},
        {{ weight_age_cap_days }}::double precision as age_cap_days,
        {{ h_short_frac }}::double precision  as h_short_frac,
        {{ h_short_min_days }}::double precision as h_short_min_days,
        {{ h_short_max_days }}::double precision as h_short_max_days,
        {{ h_long_frac }}::double precision   as h_long_frac,
        {{ h_long_min_days }}::double precision as h_long_min_days,
        {{ h_long_max_days }}::double precision as h_long_max_days,
        {{ h_pos_frac }}::double precision    as h_pos_frac,
        {{ h_pos_min_days }}::double precision  as h_pos_min_days,
        {{ h_pos_max_days }}::double precision  as h_pos_max_days
),
tenure as (
    select
        a.app_id,
        a.first_review_at,
        a.latest_review_at,
        a.record_changed_at,
        a.latest_review_updated_at,
        greatest(extract(epoch from ((select as_of_date from params) - a.first_review_at)) / 86400.0, 1.0) as tenure_days
    from app_bounds a
),
app_lambdas as (
    select
        t.app_id,
        -- Half-lives per app (linear mapping + clamps)
        least((select h_short_max_days from params),
              greatest((select h_short_min_days from params),
                       (select h_short_frac from params) * t.tenure_days)) as h_short,
        least((select h_long_max_days from params),
              greatest((select h_long_min_days from params),
                       (select h_long_frac from params) * t.tenure_days))  as h_long,
        least((select h_pos_max_days from params),
              greatest((select h_pos_min_days from params),
                       (select h_pos_frac from params) * t.tenure_days))   as h_pos
    from tenure t
),
app_lambdas_with_decay as (
    select
        app_id,
        h_short,
        h_long,
        h_pos,
        ln(2.0) / nullif(h_short, 0) as lambda_short,
        ln(2.0) / nullif(h_long, 0)  as lambda_long,
        ln(2.0) / nullif(h_pos, 0)   as lambda_pos
    from app_lambdas
),
scored as (
    select
        r.app_id,
        case when r.voted_up then 1.0 else 0.0 end as y,
        -- Age in days relative to as_of_date; cap at age_cap_days to avoid tiny-but-many weights
        least(
          extract(epoch from ((select as_of_date from params) - r.review_created_at)) / 86400.0,
          (select age_cap_days from params)
        ) as age_days
    from reviews r
),
weighted as (
    select
        s.app_id,
        -- EDP: numerator & denominator using per-app lambda_pos
        sum(s.y * exp(-al.lambda_pos   * s.age_days)) as w_pos_num,
        sum(      exp(-al.lambda_pos   * s.age_days)) as w_pos_den,
        -- Popularity momentum: exponentially-weighted counts (short vs long)
        sum(      exp(-al.lambda_short * s.age_days)) as ew_short,
        sum(      exp(-al.lambda_long  * s.age_days)) as ew_long
    from scored s
    join app_lambdas_with_decay al using (app_id)
    group by s.app_id
),
aggregated as (
    select
        s.app_id,
        count(*)::bigint as total_reviews,
        avg(s.y) as lifetime_positive_ratio
    from scored s
    group by s.app_id
)

select
    a.app_id,
    t.first_review_at,
    t.latest_review_at,
    t.latest_review_updated_at,
    t.record_changed_at,
    date_trunc('day', t.record_changed_at) as snapshot_date,
    a.total_reviews,

    -- 1) Simple review average rating (lifetime positivity)
    a.lifetime_positive_ratio as avg_rating,

    -- 2) Hold-up as "current sentiment": Adaptive EDP
    (w.w_pos_num / nullif(w.w_pos_den, 0.0)) as edp_current,

    -- 3) Decay (popularity momentum): Adaptive Exponentially-Weighted Rate Ratio
    (w.ew_short / nullif(w.ew_long, 0.0))    as decay_ewrr,

    -- 4) Cult coefficient: positivity / log1p(volume)
    (a.lifetime_positive_ratio / nullif(log(1 + a.total_reviews), 0.0)) as cult_score,

    -- Optional: expose the per-app half-lives used (helps debugging/tuning)
    al.h_short as half_life_short_days,
    al.h_long  as half_life_long_days,
    al.h_pos   as half_life_pos_days

from aggregated a
join weighted   w  using (app_id)
join tenure     t  using (app_id)
join app_lambdas al using (app_id);
