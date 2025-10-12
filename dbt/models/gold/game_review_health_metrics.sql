{{ config(materialized='table') }}

{% set early_window_days = var('early_window_days', 180) %}
{% set recent_window_days = var('recent_window_days', 180) %}
{% set decay_window_days = var('decay_window_days', 90) %}

with reviews as (
    select
        app_id,
        recommendationid,
        review_created_at,
        review_updated_at,
        record_changed_at,
        voted_up,
        helpful_votes,
        funny_votes
    from {{ ref('steam_reviews_enriched') }}
    where review_created_at is not null
      and coalesce(is_deleted, false) = false
),
window_bounds as (
    select
        app_id,
        min(review_created_at) as first_review_at,
        max(review_created_at) as latest_review_at
    from reviews
    group by app_id
),
annotated as (
    select
        r.*,
        w.first_review_at,
        w.latest_review_at,
        case
            when r.review_created_at <= w.first_review_at + interval '{{ early_window_days }} days'
                then 1
            else 0
        end as is_early_window,
        case
            when r.review_created_at >= w.latest_review_at - interval '{{ recent_window_days }} days'
                then 1
            else 0
        end as is_recent_window,
        case
            when r.review_created_at >= w.latest_review_at - interval '{{ decay_window_days }} days'
                then 1
            else 0
        end as is_recent_decay_window,
        case
            when r.review_created_at >= w.latest_review_at - interval '{{ decay_window_days * 2 }} days'
                 and r.review_created_at < w.latest_review_at - interval '{{ decay_window_days }} days'
                then 1
            else 0
        end as is_prior_decay_window
    from reviews r
    join window_bounds w using (app_id)
),
aggregated as (
    select
        app_id,
        max(first_review_at) as first_review_at,
        max(latest_review_at) as latest_review_at,
        max(record_changed_at) as record_changed_at,
        max(review_updated_at) as latest_review_updated_at,
        count(*) as total_reviews,
        avg(case when voted_up then 1.0 else 0.0 end) as lifetime_positive_ratio,
        avg(coalesce(helpful_votes, 0)) as avg_helpful_votes,
        sum(case when is_early_window = 1 and voted_up then 1 else 0 end) as early_positive_reviews,
        sum(case when is_early_window = 1 then 1 else 0 end) as early_review_count,
        sum(case when is_recent_window = 1 and voted_up then 1 else 0 end) as recent_positive_reviews,
        sum(case when is_recent_window = 1 then 1 else 0 end) as recent_review_count,
        sum(case when is_recent_decay_window = 1 then 1 else 0 end) as recent_decay_count,
        sum(case when is_prior_decay_window = 1 then 1 else 0 end) as prior_decay_count
    from annotated
    group by app_id
)

select
    app_id,
    first_review_at,
    latest_review_at,
    latest_review_updated_at,
    record_changed_at,
    date_trunc('day', record_changed_at) as snapshot_date,
    total_reviews,
    lifetime_positive_ratio,
    case
        when early_review_count = 0 then null
        else early_positive_reviews::double / early_review_count
    end as early_positive_ratio,
    case
        when recent_review_count = 0 then null
        else recent_positive_reviews::double / recent_review_count
    end as recent_positive_ratio,
    coalesce((
        case
            when recent_review_count = 0 or early_review_count = 0 then null
            else (recent_positive_reviews::double / nullif(recent_review_count, 0)) -
                 (early_positive_reviews::double / nullif(early_review_count, 0))
        end
    ), 0.0) as hold_up_score,
    recent_decay_count,
    prior_decay_count,
    (recent_decay_count + 1.0) / (prior_decay_count + 1.0) as review_decay_ratio,
    avg_helpful_votes,
    case
        when total_reviews = 0 then 0.0
        else (avg_helpful_votes * lifetime_positive_ratio) /
             greatest(log(total_reviews + 2), 1)
    end as cult_popularity_score,
    total_reviews * lifetime_positive_ratio as general_popularity_score
from aggregated
