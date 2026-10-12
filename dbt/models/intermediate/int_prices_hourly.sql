select
    date_trunc('hour', timestamp_utc) as timestamp_utc,
    avg(price_eur_mwh)                as price_eur_mwh,
    bool_or(is_negative_price)        as had_negative_price

from {{ ref('stg_prices') }}
group by 1
