-- Downsamples the 15-minute generation feed to hourly and pivots production
-- types into columns.
--
-- Two-step aggregation, and the order matters. Renewable and conventional
-- totals are summed *within each 15-minute timestamp first*, then averaged
-- across the four intervals in the hour. Doing it the other way round (summing
-- everything in the hour) would multiply the totals by four, because the values
-- are instantaneous power in MW, not energy.

with quarter_hourly_totals as (

    select
        timestamp_utc,
        sum(value_mw) filter (where is_renewable) as renewable_mw,
        sum(value_mw) filter (
            where not is_renewable and not is_aggregate_series
        ) as conventional_mw

    from {{ ref('stg_generation') }}
    group by 1

),

hourly_totals as (

    select
        date_trunc('hour', timestamp_utc) as timestamp_utc,
        avg(renewable_mw)                 as renewable_mw,
        avg(conventional_mw)              as conventional_mw

    from quarter_hourly_totals
    group by 1

),

hourly_by_type as (

    select
        date_trunc('hour', timestamp_utc) as timestamp_utc,

        avg(value_mw) filter (where production_type = 'Solar')              as solar_mw,
        avg(value_mw) filter (where production_type = 'Wind onshore')       as wind_onshore_mw,
        avg(value_mw) filter (where production_type = 'Wind offshore')      as wind_offshore_mw,
        avg(value_mw) filter (where production_type = 'Hydro Run-of-River') as hydro_mw,
        avg(value_mw) filter (where production_type = 'Biomass')            as biomass_mw,
        avg(value_mw) filter (where production_type = 'Nuclear')            as nuclear_mw,
        avg(value_mw) filter (where production_type = 'Fossil gas')         as fossil_gas_mw,
        avg(value_mw) filter (
            where production_type = 'Fossil brown coal / lignite'
        )                                                                    as lignite_mw,
        avg(value_mw) filter (where production_type = 'Fossil hard coal')   as hard_coal_mw,
        avg(value_mw) filter (where production_type = 'Load')               as load_mw,

        count(*)                                                             as source_rows

    from {{ ref('stg_generation') }}
    group by 1

)

select
    t.timestamp_utc,
    t.solar_mw,
    t.wind_onshore_mw,
    t.wind_offshore_mw,
    t.hydro_mw,
    t.biomass_mw,
    t.nuclear_mw,
    t.fossil_gas_mw,
    t.lignite_mw,
    t.hard_coal_mw,
    t.load_mw,
    h.renewable_mw,
    h.conventional_mw,
    t.source_rows

from hourly_by_type t
left join hourly_totals h on t.timestamp_utc = h.timestamp_utc
