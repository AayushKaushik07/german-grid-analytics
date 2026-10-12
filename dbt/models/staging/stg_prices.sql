with source as (

    select * from {{ source('raw', 'day_ahead_prices') }}

)

select
    timestamp_utc::timestamptz  as timestamp_utc,
    price_eur_mwh::numeric      as price_eur_mwh,
    price_eur_mwh < 0           as is_negative_price,
    ingested_at_utc::timestamptz as ingested_at_utc

from source
where price_eur_mwh is not null
