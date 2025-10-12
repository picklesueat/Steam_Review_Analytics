{{ config(materialized='view') }}

with ranked as (
    select
        appid,
        recommendationid,
        updated_at,
        ingested_at,
        load_id,
        hash_payload,
        cursor,
        payload,
        row_number() over (
            partition by appid, recommendationid, hash_payload
            order by coalesce(updated_at, ingested_at) desc, ingested_at desc, load_id desc
        ) as row_num
    from {{ ref('steam_reviews_raw') }}
)

select
    appid,
    recommendationid,
    updated_at,
    ingested_at,
    load_id,
    hash_payload,
    cursor,
    payload
from ranked
where row_num = 1
