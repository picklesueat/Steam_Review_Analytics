{{ config(materialized='view') }}

select
    appid,
    recommendationid,
    updated_at,
    ingested_at,
    load_id,
    hash_payload,
    cursor,
    payload
from {{ source('bronze', 'steam_reviews_raw') }}
