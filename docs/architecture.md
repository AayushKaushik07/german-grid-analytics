# Architecture and design decisions

Written as a record of *why*, not *what*. The what is in the code.

## Why these two sources

A single dataset makes for a plumbing exercise. Two independent sources with
different grains, different timestamp conventions and a non-trivial join key
make for an engineering problem — which is the point.

The pairing is also analytically necessary. Generation data alone tells you
what happened; joined against weather, it tells you *why*, and lets the wind
capacity curve (Q3) exist at all.

## Why UTC everywhere in raw and staging

German electricity data is published in local time. `Europe/Berlin` has two DST
transitions a year: in October 02:00–03:00 occurs twice, in March it never
occurs. A pipeline keyed on local timestamps therefore produces duplicate keys
one day a year and a gap another.

Rule applied throughout: **store UTC, derive local for presentation.**
`fct_grid_hourly` carries both `timestamp_utc` (the key) and `timestamp_local`
(what a German analyst reasons in). The uniqueness test sits on the UTC column.

## Why delete-then-insert rather than append or upsert

Append duplicates on retry. Upsert needs a stable natural key, and the
15-minute generation feed is occasionally revised upstream, which means a key
can legitimately change value after the fact.

Delete-then-insert over the ingested window gives idempotency with no key
management: rerunning any window replaces it. The cost is that the delete needs
an index on `timestamp_utc` to stay fast — see `sql/maintenance/indexes.sql`.

## Why dbt rather than SQL scripts or pandas

Three things it provides that hand-written SQL does not:

1. **Dependency resolution.** `ref()` builds the DAG; models run in the right
   order without a hand-maintained numbered-file convention.
2. **Tests as part of the build.** `dbt build` interleaves models and their
   tests, so a failing assertion stops the run instead of quietly producing a
   wrong dashboard.
3. **Documentation that cannot drift.** `dbt docs generate` reads the same YAML
   that defines the tests, so the lineage graph is always current.

Transformation stays in SQL rather than pandas because the data must live in
Postgres for Power BI anyway. Pulling it into Python only to push it back is
a round trip with no benefit at this volume.

## Why ephemeral intermediates

`int_generation_hourly` and `int_prices_hourly` are inlined as CTEs rather than
materialised. They exist for readability, are each consumed by exactly one
downstream model, and are of no interest to a BI user. Materialising them would
add storage and a refresh step for no gain.

## Why a star schema in marts

Power BI's engine is built for star schemas. A wide fact table plus a proper
date dimension means time-intelligence functions work natively, relationships
stay single-direction, and the model does not need DAX workarounds for
year-over-year comparisons.

`fct_daily_summary` is redundant in principle — Power BI could roll up the
hourly table itself — but a multi-year hourly table is millions of rows, and
pre-aggregating keeps trend visuals responsive on a laptop.

## Known limitations

Stated plainly, because a portfolio project that claims no limitations is not
credible.

- **One weather point for the whole country.** Weather is sampled at the German
  centroid (51.16 N, 10.45 E). Real wind generation is dominated by the north
  and offshore; solar by the south. This weakens the Q3 capacity curve. The
  honest fix is a capacity-weighted average over several points, which is the
  first thing I would add next.
- **No generation forecast data.** Only actuals. Forecast-vs-actual error
  would be the natural next analysis and the Energy-Charts
  `public_power_forecast` endpoint supports it.
- **Prices are day-ahead only.** Intraday and balancing markets are excluded,
  so "the price" here is one of several.
- **No orchestrator.** A cron line plus idempotent loads is proportionate at
  this scale. At more sources or real SLAs, Airflow or Dagster would earn its
  operational cost; here it would be resume decoration.
- **Renewable classification is hardcoded.** If Energy-Charts introduces a new
  production type, it falls into "conventional" by default. The `source_rows`
  column on the intermediate model exists so an unexpected change in type count
  is at least visible.

## What I would add with more time

1. Capacity-weighted weather across 5–10 points
2. Forecast-vs-actual error as a sixth question
3. dbt snapshots on the price feed to capture upstream revisions
4. An incremental materialisation on `fct_grid_hourly` once the backfill spans
   several years, so daily runs stop rebuilding history
