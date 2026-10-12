-- Cleans the raw generation feed: types the columns, classifies each series,
-- and drops the aggregate rows that would otherwise be double counted.

with source as (

    select * from {{ source('raw', 'generation') }}

),

cleaned as (

    select
        timestamp_utc::timestamptz                          as timestamp_utc,
        trim(production_type)                               as production_type,
        value_mw::numeric                                   as value_mw,
        ingested_at_utc::timestamptz                        as ingested_at_utc,

        -- Series that are not power plant output, although the API returns them
        -- inside the same array as real generators: demand and share series,
        -- net cross-border flows (negative = export) and the power drawn by
        -- pumped storage (always negative). Excluded from every generation total.
        production_type in (
            'Load', 'Residual load',
            'Renewable share of generation', 'Renewable share of load',
            'Cross border electricity trading', 'Hydro pumped storage consumption'
        )                                                   as is_aggregate_series,

        production_type in (
            'Solar', 'Wind onshore', 'Wind offshore',
            'Hydro Run-of-River', 'Hydro water reservoir',
            'Biomass', 'Geothermal', 'Waste'
        )                                                   as is_renewable

    from source
    where value_mw is not null

)

select * from cleaned
