# Findings

Results of [`analysis/insights.sql`](../analysis/insights.sql) on the full backfill:
**January 2024 – December 2025**, 1.47 million generation rows (15-minute grain, 21
production types) plus day-ahead prices and hourly weather, modelled into 17,544 hourly
rows. "Renewable share" means renewable generation divided by load (demand).

## 1. The renewable share did not grow — it held flat near 57 %

The 12-month average of the monthly renewable share was **56.95 % for 2024** and
**56.91 % for 2025**. Within 2025 the rolling average never left the band of
**53.8 % – 57.0 %**.

Individual months tell a very different story. The share fell to **43.0 % in
February 2025** and peaked at **72.2 % in June 2025**, a swing of **29 percentage
points** within a single year. Compared with the same month a year earlier, February
2025 was 18.2 points down and June 2025 was 13.4 points up.

**So what:** a single month says almost nothing about progress. Comparing one month with
the previous month mixes weather with trend. Only a 12-month window or a same-month
comparison separates the two, and on that basis 2025 was no better than 2024.

## 2. A strict Dunkelflaute threshold finds exactly one event

Only **one** stretch of six or more consecutive hours stayed below 15 % renewable
coverage in two years: **6 November 2024, 16:00–22:00** (7 hours, average 14.0 %),
an evening with almost no wind and no sun. It matches the widely reported Dunkelflaute
of early November 2024, and November 2024 was the weakest month of that year
(46.6 %).

**So what:** the threshold here counts *all* renewables. Biomass, run-of-river hydro and
waste deliver a few gigawatts around the clock, so total renewable coverage rarely drops
below 15 % even when wind and solar collapse. A definition based on wind and solar alone
would find more events. Which definition is "right" depends on the question: for sizing
storage and backup capacity, the wind-and-solar view is the more useful one.

## 3. The wind power curve is clearly non-linear

Average wind output across Germany, by wind speed at 100 m at the reference point:

| Wind speed | Average output |
|---|---|
| 1 m/s | 6.3 GW |
| 6 m/s | 17.1 GW |
| 11 m/s | 36.1 GW |
| 14 m/s | 42.8 GW |

Output rises slowly at low wind speeds, steepest between roughly **6 and 11 m/s**
(about 3.8 GW per m/s), and flattens above that (about 2.2 GW per m/s from 11 to 14 m/s).

A high-speed cut-out is **not** visible. Wind speeds above 15 m/s at the single
reference point are too rare (fewer than 50 hours) to form a reliable bucket, and the
national output sums tens of thousands of turbines in very different wind conditions.

**So what:** a linear model of wind output against wind speed would misforecast at both
ends. Seeing the cut-out would need wind speeds at several locations (see the
limitations in [`architecture.md`](architecture.md)).

## 4. A high renewable share pushes the day-ahead price down — and below zero

| Renewable share decile | Share range | Average price | Hours with negative price |
|---|---|---|---|
| lowest (1) | 13.6 – 27.1 % | 151.12 EUR/MWh | 0 % |
| middle (5) | 47.6 – 54.3 % | 95.36 EUR/MWh | 0 % |
| 9 | 78.6 – 91.5 % | 37.91 EUR/MWh | 5.9 % |
| highest (10) | 91.5 – 130.6 % | -0.04 EUR/MWh | 53.2 % |

The average price falls with every decile. Negative prices practically only occur when
renewables cover more than about 70 % of demand (8 hours in decile 8, none below it); in the top decile more than half of all
hours (933 of 1,754) had a negative price.

**So what:** the merit-order effect is visible directly in the data, without any
modelling. It also shows why flexible demand and storage are worth money: the same
megawatt-hour costs around 150 EUR in the least renewable hours and nothing in the most
renewable ones.

## 5. The duck curve is a summer phenomenon

**Summer (June – August):** residual load (demand minus renewables) bottoms out at
**14:00 local time at 4.4 GW on average**, about 22 GW below the 07:00 value (26.2 GW)
and 28 GW below the evening peak at 20:00 (32.2 GW). Prices follow the same curve:
14.91 EUR/MWh at 14:00 against 147.14 EUR/MWh at 20:00.

**Winter (December – February):** the midday dip is shallow. Residual load falls only
from 31.4 GW (08:00) to 26.2 GW (12:00) and peaks at 35.4 GW at 17:00. Wind delivers
19–22 GW throughout the day and solar adds at most 11 GW.

**So what:** the flexibility problem is a *daily* one in summer (shift energy from noon to
the evening) and a *multi-day* one in winter (calm, dark periods), and those need
different solutions: batteries for the first, dispatchable capacity or long-duration
storage for the second.

---

## Caveats on all of the above

Read [`architecture.md`](architecture.md) first. In particular, the single weather
sampling point weakens finding 3 more than the others, and the renewable classification
follows the source's production types (all waste is counted as renewable).
