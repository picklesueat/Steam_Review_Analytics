{{ config(
    materialized='incremental',
    unique_key='recommendationid',
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns'
) }}

with bronze as (
    select
        appid,
        recommendationid,
        updated_at,
        ingested_at,
        load_id,
        hash_payload,
        cursor,
        payload
    from {{ ref('steam_reviews_raw_compacted') }} src
    {% if is_incremental() %}
    where coalesce(updated_at, ingested_at) > (
        select coalesce(max(record_changed_at), timestamp '1970-01-01') from {{ this }}
    ) - interval '2 days'
        OR not exists (
        select 1
        from {{ this }} t
        where t.recommendationid = src.recommendationid
          and t.app_id = src.appid     -- if target column is app_id; change to t.appid if not renamed
    )
    {% endif %}
),
normalized as (
    select
        recommendationid,
        appid as app_id,
        payload ->> 'language' as review_language,
        payload ->> 'review' as review,
        try_cast(payload ->> 'timestamp_created' as double) as created_epoch,
        try_cast(payload ->> 'timestamp_updated' as double) as updated_epoch,
        try_cast(payload ->> 'fetched_at' as timestamp) as fetched_at,
        coalesce(try_cast(payload ->> 'voted_up' as boolean), false) as voted_up,
        coalesce(try_cast(payload ->> 'votes_up' as integer), 0) as helpful_votes,
        coalesce(try_cast(payload ->> 'votes_funny' as integer), 0) as funny_votes,
        try_cast(payload ->> 'weighted_vote_score' as double) as weighted_vote_score,
        coalesce(try_cast(payload ->> 'comment_count' as integer), 0) as comment_count,
        coalesce(try_cast(payload ->> 'steam_purchase' as boolean), false) as steam_purchase,
        coalesce(try_cast(payload ->> 'received_for_free' as boolean), false) as received_for_free,
        coalesce(try_cast(payload ->> 'written_during_early_access' as boolean), false) as written_during_early_access,
        coalesce(try_cast(payload ->> 'playtime_at_review' as integer), 0) as playtime_at_review_minutes,
        (payload -> 'author') ->> 'steamid' as author_steam_id,
        coalesce(try_cast((payload -> 'author') ->> 'num_games_owned' as integer), 0) as author_games_owned,
        coalesce(try_cast((payload -> 'author') ->> 'num_reviews' as integer), 0) as author_review_count,
        coalesce(try_cast((payload -> 'author') ->> 'playtime_forever' as integer), 0) as author_playtime_forever_minutes,
        coalesce(try_cast((payload -> 'author') ->> 'playtime_last_two_weeks' as integer), 0) as author_playtime_last_two_weeks_minutes,
        coalesce(try_cast((payload -> 'author') ->> 'playtime_at_review' as integer), 0) as author_playtime_at_review_minutes,
        try_cast((payload -> 'author') ->> 'last_played' as double) as author_last_played_epoch,
        try_cast(payload ->> 'page' as integer) as page,
        cursor,
        updated_at,
        ingested_at,
        load_id,
        hash_payload
    from bronze
)

select
    recommendationid,
    app_id,
    review_language,
    review,
    to_timestamp(created_epoch) as review_created_at,
    coalesce(to_timestamp(updated_epoch), updated_at) as review_updated_at,
    fetched_at,
    voted_up,
    helpful_votes,
    funny_votes,
    weighted_vote_score,
    comment_count,
    steam_purchase,
    received_for_free,
    written_during_early_access,
    playtime_at_review_minutes,
    author_steam_id,
    author_games_owned,
    author_review_count,
    author_playtime_forever_minutes,
    author_playtime_last_two_weeks_minutes,
    author_playtime_at_review_minutes,
    author_last_played_epoch,
    to_timestamp(author_last_played_epoch) as author_last_played_at,
    page,
    cursor,
    coalesce(to_timestamp(updated_epoch), updated_at, to_timestamp(created_epoch), ingested_at) as record_changed_at,
    ingested_at as bronze_ingested_at,
    load_id as bronze_load_id,
    hash_payload as bronze_hash_payload,
    false as is_deleted
from normalized
