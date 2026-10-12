# Data dictionary

## marts.fct_grid_hourly

Grain: one row per hour, UTC. Primary key `timestamp_utc`.

| Column | Type | Description |
|---|---|---|
| `timestamp_utc` | timestamptz | Hour start, UTC. Primary key. |
| `timestamp_local` | timestamp | Same instant in `Europe/Berlin`. Presentation only. |
| `date_day` | date | Local calendar date. Joins to `dim_date`. |
| `hour_local` | int | 0–23, local time. |
| `solar_mw` | numeric | Mean solar output during the hour, MW. |
| `wind_onshore_mw` | numeric | Mean onshore wind output, MW. |
| `wind_offshore_mw` | numeric | Mean offshore wind output, MW. |
| `wind_total_mw` | numeric | Onshore + offshore. |
| `hydro_mw` | numeric | Run-of-river hydro, MW. |
| `biomass_mw` | numeric | Biomass, MW. |
| `nuclear_mw` | numeric | Nuclear, MW. Always null for 2024 onwards: Germany's last reactors closed in April 2023 and the source no longer publishes the series. |
| `fossil_gas_mw` | numeric | Gas-fired generation, MW. |
| `lignite_mw` | numeric | Brown coal, MW. |
| `hard_coal_mw` | numeric | Hard coal, MW. |
| `renewable_mw` | numeric | All renewable technologies summed. |
| `conventional_mw` | numeric | All non-renewable generators summed (fossil, pumped-storage generation, others). Excludes cross-border trade and pumped-storage consumption. |
| `load_mw` | numeric | German electricity demand, MW. |
| `residual_load_mw` | numeric | `load_mw - renewable_mw`. Demand dispatchable plants must cover. Can be negative. |
| `renewable_share_of_load_pct` | numeric | `100 * renewable_mw / load_mw`. Can exceed 100 during high-wind, low-demand hours. |
| `is_low_renewable_hour` | boolean | Renewable share below 15%. The Dunkelflaute flag. |
| `price_eur_mwh` | numeric | Day-ahead auction price, DE-LU zone. **Legitimately negative** at times. |
| `had_negative_price` | boolean | Any negative 15-minute price in the hour. |
| `temperature_c` | numeric | 2 m air temperature, °C. |
| `wind_speed_100m_ms` | numeric | Wind speed at 100 m hub height, m/s (converted from km/h). |
| `shortwave_radiation_wm2` | numeric | Global horizontal irradiance, W/m². |
| `cloud_cover_pct` | numeric | Total cloud cover, 0–100. |

## marts.fct_daily_summary

Grain: one row per local calendar day. Primary key `date_day`.

Key columns: `load_gwh`, `renewable_gwh`, `renewable_share_of_load_pct`,
`peak_load_mw`, `avg_price_eur_mwh`, `negative_price_hours`,
`low_renewable_hours`, `hours_observed`.

`hours_observed` is 24 on normal days, 23 or 25 on DST switch days. That is
expected, not an error.

## marts.dim_date

Standard date dimension: `date_day`, `year`, `quarter`, `month_number`,
`month_short`, `iso_week`, `day_of_week`, `day_short`, `is_weekend`, `season`.
Mark this as the date table in Power BI.

## Units, stated once

- Power is **MW** (instantaneous). Energy is **GWh** (accumulated).
- Hourly mean MW equals MWh delivered in that hour, which is why hourly values
  are averaged rather than summed.
- Prices are **EUR/MWh**, DE-LU bidding zone.

## Attribution

Generation and price data: Energy-Charts, Fraunhofer ISE, CC BY 4.0.
Weather data: Open-Meteo ERA5 reanalysis, CC BY 4.0.
