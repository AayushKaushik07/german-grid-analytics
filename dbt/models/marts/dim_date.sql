{{ config(materialized='table') }}

-- Conventional date dimension so Power BI can mark a proper date table and use
-- time-intelligence functions (YoY, running totals) without DAX workarounds.

with bounds as (
    select
        min(timestamp_utc)::date as min_date,
        max(timestamp_utc)::date as max_date
    from {{ ref('int_generation_hourly') }}
),

spine as (
    select generate_series(min_date, max_date, interval '1 day')::date as date_day
    from bounds
)

select
    date_day,
    extract(year    from date_day)::int  as year,
    extract(quarter from date_day)::int  as quarter,
    extract(month   from date_day)::int  as month_number,
    to_char(date_day, 'Mon')             as month_short,
    extract(week    from date_day)::int  as iso_week,
    extract(isodow  from date_day)::int  as day_of_week,
    to_char(date_day, 'Dy')              as day_short,
    extract(isodow from date_day) in (6, 7) as is_weekend,
    case
        when extract(month from date_day) in (12, 1, 2) then 'Winter'
        when extract(month from date_day) in (3, 4, 5)  then 'Spring'
        when extract(month from date_day) in (6, 7, 8)  then 'Summer'
        else 'Autumn'
    end as season

from spine
