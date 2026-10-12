{{ config(materialized='table') }}

-- Pre-aggregated daily grain. Power BI could roll this up itself, but a daily
-- table keeps the multi-year trend visuals responsive on a laptop.

select
    date_day,

    avg(load_mw)                        as avg_load_mw,
    max(load_mw)                        as peak_load_mw,
    avg(renewable_mw)                   as avg_renewable_mw,
    avg(solar_mw)                       as avg_solar_mw,
    avg(wind_total_mw)                  as avg_wind_mw,
    avg(residual_load_mw)               as avg_residual_load_mw,

    -- Energy in GWh: hourly MW averages summed over the day, divided by 1000.
    round(sum(load_mw) / 1000.0, 2)     as load_gwh,
    round(sum(renewable_mw) / 1000.0, 2) as renewable_gwh,

    round(100.0 * sum(renewable_mw) / nullif(sum(load_mw), 0), 2)
                                        as renewable_share_of_load_pct,

    avg(price_eur_mwh)                  as avg_price_eur_mwh,
    min(price_eur_mwh)                  as min_price_eur_mwh,
    max(price_eur_mwh)                  as max_price_eur_mwh,
    count(*) filter (where had_negative_price) as negative_price_hours,
    count(*) filter (where is_low_renewable_hour) as low_renewable_hours,

    avg(wind_speed_100m_ms)             as avg_wind_speed_ms,
    avg(temperature_c)                  as avg_temperature_c,
    count(*)                            as hours_observed

from {{ ref('fct_grid_hourly') }}
group by 1
