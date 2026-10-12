# Power BI report

`grid_analytics.pbix` is a three-page report on the `marts` schema. The data is imported,
so the file opens and shows the 2024–2025 results without a running database. Screenshots
of every page are in [`screenshots/`](screenshots/).

| Page | What it answers |
|---|---|
| **Overview** | KPI cards (renewable share, average load, average day-ahead price, negative-price hours); renewable share monthly vs. rolling 12 months; monthly generation mix in TWh |
| **Prices** | Average price and share of negative-price hours by 10 % band of renewable share; negative-price hours and average price by month |
| **Daily profile** | Residual load and day-ahead price by hour of day, one line per season (the duck curve) |

## Refreshing with your own data

1. Start Postgres and load data: `make up`, `make backfill ...`, `make dbt`
2. Open `grid_analytics.pbix` → **Home → Refresh**. Credentials: the `POSTGRES_USER` /
   `POSTGRES_PASSWORD` from your `.env`.
3. If you point it at another server: **Transform data → Data source settings → Change
   source**.

Use `127.0.0.1:5432`, not `localhost:5432`. On Windows with Docker Desktop, `localhost`
can resolve to IPv6 first, and the connection then hangs without an error.

Only the `marts` schema is used. Never connect a report to `raw` or `staging`; those
layers exist to be rebuilt.

## Model

- `fct_grid_hourly` (one row per hour) and `fct_daily_summary` (one row per day), both
  related many-to-one to `dim_date[date_day]`
- `dim_date` is marked as the date table, so time-intelligence DAX works
- Calculated columns: `dim_date[Month]` (first day of the month, for monthly axes),
  `fct_grid_hourly[Renewable Share Band]` (10 % bands, capped at 120 %) and
  `fct_grid_hourly[Hour of Day]`

## Measures

```dax
Renewable Share % =
DIVIDE(SUM(fct_daily_summary[renewable_gwh]), SUM(fct_daily_summary[load_gwh])) * 100

-- blank until a full 12 months of data is available, so the line does not
-- start with a misleading partial-window average
Rolling 12M Renewable Share % =
VAR _end = MAX(dim_date[date_day])
VAR _first = CALCULATE(MIN(fct_daily_summary[date_day]), ALL(dim_date), ALL(fct_daily_summary))
RETURN IF(_end < EDATE(_first, 12) - 1, BLANK(),
    CALCULATE([Renewable Share %], DATESINPERIOD(dim_date[date_day], _end, -12, MONTH)))

Renewable Share YoY (pp) =
VAR _prior = CALCULATE([Renewable Share %], SAMEPERIODLASTYEAR(dim_date[date_day]))
RETURN IF(ISBLANK(_prior), BLANK(), [Renewable Share %] - _prior)

Negative Price Hours =
CALCULATE(COUNTROWS(fct_grid_hourly), fct_grid_hourly[had_negative_price] = TRUE())

Negative Price Share % = DIVIDE([Negative Price Hours] + 0, COUNTROWS(fct_grid_hourly)) * 100

Wind (TWh) = SUM(fct_grid_hourly[wind_total_mw]) / 1000000   -- hourly MW averages = MWh
```

Also in the model: `Avg Load (GW)`, `Avg Residual Load (GW)`, `Avg Price (EUR/MWh)`,
`Low-Renewable Hours`, `Solar (TWh)`, `Other Renewables (TWh)`, `Conventional (TWh)`,
`Load (TWh)`, and per-season variants of residual load and price for the daily profile page.

The rolling 12-month line is energy-weighted (total renewable GWh ÷ total load GWh over the
window), so it can differ by a few tenths of a point from the SQL in
`analysis/insights.sql`, which averages the twelve monthly shares.
