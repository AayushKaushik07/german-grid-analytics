"""Reshape raw API payloads into tidy, load-ready DataFrames.

Every function here is pure: JSON in, DataFrame out, no network and no database.
That is what makes the test suite in ``tests/`` fast and offline-runnable.

Design notes
------------
* All timestamps are converted to timezone-aware UTC. German data is published
  in local time with two DST switches a year -- storing local time would create
  one duplicated hour in October and one missing hour in March. We normalise to
  UTC on ingest and let the dbt layer derive Europe/Berlin local time for
  reporting.
* Energy-Charts returns generation at 15-minute resolution, Open-Meteo at
  hourly. We keep the native grain in the raw tables and resample in dbt, so no
  information is thrown away before it reaches the warehouse.
* ``Load`` and ``Residual load`` arrive inside the same ``production_types``
  array as real generators. They are consumption series, not generation, so
  they are tagged separately rather than silently summed into the mix.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

# Series that Energy-Charts ships alongside generators but which are not
# generation. Keeping this list explicit prevents a silent double count.
NON_GENERATION_SERIES = {
    "Load",
    "Residual load",
    "Renewable share of generation",
    "Renewable share of load",
}

RENEWABLE_TYPES = {
    "Solar",
    "Wind onshore",
    "Wind offshore",
    "Hydro Run-of-River",
    "Hydro water reservoir",
    "Biomass",
    "Geothermal",
    "Waste",
}


def _to_utc(unix_seconds: list[int]) -> pd.DatetimeIndex:
    return pd.to_datetime(pd.Series(unix_seconds), unit="s", utc=True)


def parse_public_power(payload: dict[str, Any]) -> pd.DataFrame:
    """Flatten the column-oriented payload into one row per (timestamp, type).

    Returns columns: ``timestamp_utc``, ``production_type``, ``value_mw``.
    """
    if "unix_seconds" not in payload or "production_types" not in payload:
        raise ValueError("Unexpected public_power payload: missing required keys")

    timestamps = _to_utc(payload["unix_seconds"])
    frames: list[pd.DataFrame] = []

    for series in payload["production_types"]:
        values = series.get("data", [])
        if len(values) != len(timestamps):
            raise ValueError(
                f"Series '{series.get('name')}' has {len(values)} values but "
                f"{len(timestamps)} timestamps -- refusing to load misaligned data"
            )
        frames.append(
            pd.DataFrame(
                {
                    "timestamp_utc": timestamps,
                    "production_type": series["name"],
                    "value_mw": pd.to_numeric(values, errors="coerce"),
                }
            )
        )

    if not frames:
        return pd.DataFrame(columns=["timestamp_utc", "production_type", "value_mw"])

    out = pd.concat(frames, ignore_index=True)
    return out.sort_values(["timestamp_utc", "production_type"]).reset_index(drop=True)


def parse_prices(payload: dict[str, Any]) -> pd.DataFrame:
    """Return columns: ``timestamp_utc``, ``price_eur_mwh``."""
    if "unix_seconds" not in payload or "price" not in payload:
        raise ValueError("Unexpected price payload: missing required keys")

    timestamps = _to_utc(payload["unix_seconds"])
    prices = payload["price"]
    if len(prices) != len(timestamps):
        raise ValueError("Price array is misaligned with its timestamp array")

    return (
        pd.DataFrame(
            {
                "timestamp_utc": timestamps,
                "price_eur_mwh": pd.to_numeric(prices, errors="coerce"),
            }
        )
        .sort_values("timestamp_utc")
        .reset_index(drop=True)
    )


def parse_weather(payload: dict[str, Any]) -> pd.DataFrame:
    """Return one row per hour with the selected weather variables."""
    hourly = payload.get("hourly")
    if not hourly or "time" not in hourly:
        raise ValueError("Unexpected weather payload: missing 'hourly.time'")

    frame = pd.DataFrame(hourly)
    frame["timestamp_utc"] = pd.to_datetime(frame.pop("time"), utc=True)

    renamed = {
        "temperature_2m": "temperature_c",
        "wind_speed_100m": "wind_speed_100m_kmh",
        "shortwave_radiation": "shortwave_radiation_wm2",
        "cloud_cover": "cloud_cover_pct",
    }
    frame = frame.rename(columns=renamed)

    ordered = ["timestamp_utc", *[c for c in renamed.values() if c in frame.columns]]
    return frame[ordered].sort_values("timestamp_utc").reset_index(drop=True)


def add_ingested_at(frame: pd.DataFrame) -> pd.DataFrame:
    """Stamp every row with the load time so reloads are auditable."""
    out = frame.copy()
    out["ingested_at_utc"] = pd.Timestamp.now(tz="UTC")
    return out
