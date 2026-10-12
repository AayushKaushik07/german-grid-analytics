{{ config(materialized='table') }}

-- The central fact table: one row per hour, joining generation, price and
-- weather. Everything Power BI needs for the hourly view lives here.

with joined as (

    select
        g.timestamp_utc,
        g.solar_mw,
        g.wind_onshore_mw,
        g.wind_offshore_mw,
        g.hydro_mw,
        g.biomass_mw,
        g.nuclear_mw,
        g.fossil_gas_mw,
        g.lignite_mw,
        g.hard_coal_mw,
        g.load_mw,
        g.renewable_mw,
        g.conventional_mw,
        p.price_eur_mwh,
        p.had_negative_price,
        w.temperature_c,
        w.wind_speed_100m_ms,
        w.shortwave_radiation_wm2,
        w.cloud_cover_pct

    from {{ ref('int_generation_hourly') }} g
    left join {{ ref('int_prices_hourly') }} p on g.timestamp_utc = p.timestamp_utc
    left join {{ ref('stg_weather') }}       w on g.timestamp_utc = w.timestamp_utc

),

derived as (

    select
        *,

        -- Local time is what a German analyst reasons in; UTC is what we store.
        (timestamp_utc at time zone 'Europe/Berlin')          as timestamp_local,
        (timestamp_utc at time zone 'Europe/Berlin')::date    as date_day,
        extract(hour from timestamp_utc at time zone 'Europe/Berlin')::int as hour_local,

        coalesce(wind_onshore_mw, 0) + coalesce(wind_offshore_mw, 0) as wind_total_mw,

        -- Residual load: the demand that dispatchable plants must still cover.
        load_mw - coalesce(renewable_mw, 0)                   as residual_load_mw,

        case
            when load_mw > 0
            then round(100.0 * coalesce(renewable_mw, 0) / load_mw, 2)
        end as renewable_share_of_load_pct

    from joined

)

select
    *,
    -- A low-renewable (Dunkelflaute-like) hour: all renewables together cover
    -- under 15% of demand.
    case
        when renewable_share_of_load_pct is not null
        then renewable_share_of_load_pct < 15
    end as is_low_renewable_hour

from derived
