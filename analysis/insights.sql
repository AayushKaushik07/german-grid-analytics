-- ============================================================================
-- analysis/insights.sql
--
-- The five questions this project set out to answer. Each block runs standalone
-- against the marts schema. Findings are written up in docs/findings.md.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- Q1. How has the renewable share of demand moved, month over month and
--     year over year?
-- ----------------------------------------------------------------------------
with monthly as (

    select
        date_trunc('month', date_day)::date              as month,
        round(100.0 * sum(renewable_gwh)
              / nullif(sum(load_gwh), 0), 2)             as renewable_share_pct,
        sum(load_gwh)                                    as load_gwh

    from marts.fct_daily_summary
    group by 1

)

select
    month,
    renewable_share_pct,
    load_gwh,
    renewable_share_pct - lag(renewable_share_pct) over (order by month)
        as change_vs_prev_month_pp,
    renewable_share_pct - lag(renewable_share_pct, 12) over (order by month)
        as change_vs_same_month_last_year_pp,
    -- Only report the rolling average once a full 12 months are available.
    -- Without this guard the window silently averages however many rows exist,
    -- so the first 11 months show an expanding average that looks like a
    -- downward trend but is purely an artifact of the window filling up.
    case
        when count(*) over (
            order by month rows between 11 preceding and current row
        ) = 12
        then round(avg(renewable_share_pct) over (
            order by month rows between 11 preceding and current row
        ), 2)
    end as rolling_12m_share_pct

from monthly
order by month;


-- ----------------------------------------------------------------------------
-- Q2. Dunkelflaute: how often does the grid run on under 15% renewables for
--     six or more consecutive hours, and when?
--
--     Uses the gaps-and-islands pattern: subtracting a dense row number from a
--     sequence number turns consecutive flagged rows into a constant group key.
-- ----------------------------------------------------------------------------
with flagged as (

    select
        timestamp_local,
        renewable_share_of_load_pct,
        is_low_renewable_hour,
        row_number() over (order by timestamp_local) as overall_row,
        row_number() over (
            partition by is_low_renewable_hour order by timestamp_local
        ) as group_row

    from marts.fct_grid_hourly
    where renewable_share_of_load_pct is not null

),

islands as (

    select
        is_low_renewable_hour,
        overall_row - group_row              as island_id,
        min(timestamp_local)                 as started_at,
        max(timestamp_local)                 as ended_at,
        count(*)                             as duration_hours,
        round(avg(renewable_share_of_load_pct), 1) as avg_renewable_share_pct

    from flagged
    where is_low_renewable_hour
    group by 1, 2

)

select
    started_at,
    ended_at,
    duration_hours,
    avg_renewable_share_pct
from islands
where duration_hours >= 6
order by duration_hours desc
limit 25;


-- ----------------------------------------------------------------------------
-- Q3. The wind capacity curve: how does hourly wind output track wind speed?
--     Bucketing by 1 m/s reveals the characteristic S-curve, including the
--     cut-out at high speeds where turbines feather to protect themselves.
-- ----------------------------------------------------------------------------
select
    floor(wind_speed_100m_ms)::int          as wind_speed_bucket_ms,
    count(*)                                as observed_hours,
    round(avg(wind_total_mw))               as avg_wind_output_mw,
    round(percentile_cont(0.5) within group (order by wind_total_mw)::numeric) as median_wind_mw,
    round(max(wind_total_mw))               as max_wind_output_mw

from marts.fct_grid_hourly
where wind_speed_100m_ms is not null
  and wind_total_mw is not null
group by 1
having count(*) >= 50   -- drop thinly observed extremes
order by 1;


-- ----------------------------------------------------------------------------
-- Q4. Does a high renewable share actually push the day-ahead price down?
--     Deciles of renewable share against the price distribution.
-- ----------------------------------------------------------------------------
with bucketed as (

    select
        ntile(10) over (order by renewable_share_of_load_pct) as share_decile,
        renewable_share_of_load_pct,
        price_eur_mwh,
        had_negative_price

    from marts.fct_grid_hourly
    where renewable_share_of_load_pct is not null
      and price_eur_mwh is not null

)

select
    share_decile,
    round(min(renewable_share_of_load_pct), 1)  as share_from_pct,
    round(max(renewable_share_of_load_pct), 1)  as share_to_pct,
    count(*)                                    as hours,
    round(avg(price_eur_mwh), 2)                as avg_price_eur_mwh,
    round(percentile_cont(0.5) within group (order by price_eur_mwh)::numeric, 2)
                                                as median_price_eur_mwh,
    count(*) filter (where had_negative_price)  as negative_price_hours,
    round(100.0 * count(*) filter (where had_negative_price) / count(*), 1)
                                                as negative_price_share_pct

from bucketed
group by 1
order by 1;


-- ----------------------------------------------------------------------------
-- Q5. When during the day is the grid most and least renewable? The classic
--     duck-curve shape, split by season so the solar effect is visible.
-- ----------------------------------------------------------------------------
select
    d.season,
    f.hour_local,
    round(avg(f.renewable_share_of_load_pct), 1) as avg_renewable_share_pct,
    round(avg(f.solar_mw))                       as avg_solar_mw,
    round(avg(f.wind_total_mw))                  as avg_wind_mw,
    round(avg(f.residual_load_mw))               as avg_residual_load_mw,
    round(avg(f.price_eur_mwh), 2)               as avg_price_eur_mwh

from marts.fct_grid_hourly f
join marts.dim_date d on f.date_day = d.date_day
group by 1, 2
order by
    case d.season
        when 'Winter' then 1 when 'Spring' then 2
        when 'Summer' then 3 else 4
    end,
    f.hour_local;
