with source as (

    select * from {{ source('raw', 'weather') }}

)

select
    timestamp_utc::timestamptz          as timestamp_utc,
    temperature_c::numeric              as temperature_c,
    -- Open-Meteo returns km/h; convert to m/s, the unit used in wind power curves.
    (wind_speed_100m_kmh::numeric / 3.6) as wind_speed_100m_ms,
    shortwave_radiation_wm2::numeric    as shortwave_radiation_wm2,
    cloud_cover_pct::numeric            as cloud_cover_pct

from source
