"""Seed the CI database with a deterministic synthetic slice.

CI must not depend on a live third-party API: an upstream outage would turn
every pull request red for reasons unrelated to the code. This script generates
14 days of realistically shaped data -- solar following a daily curve, wind
following a slow random walk, load with a weekday/weekend pattern -- so that
``dbt build`` exercises the real models and the real tests.

Not used in production. The daily job pulls the genuine feeds.
"""

from __future__ import annotations

import math
import random
from datetime import UTC, datetime, timedelta

import pandas as pd

from ingestion.config import load_settings
from ingestion.loaders import ensure_schema, get_engine, load_frame

DAYS = 14
SEED = 42

RENEWABLE_TYPES = ["Solar", "Wind onshore", "Wind offshore", "Biomass"]
CONVENTIONAL_TYPES = ["Fossil gas", "Fossil hard coal", "Fossil brown coal / lignite"]


def _solar_mw(hour: int) -> float:
    """Bell curve peaking at midday, zero at night."""
    if hour < 6 or hour > 20:
        return 0.0
    return 35_000 * math.sin(math.pi * (hour - 6) / 14) ** 2


def _load_mw(hour: int, is_weekend: bool) -> float:
    base = 52_000 if not is_weekend else 45_000
    morning = 8_000 * math.exp(-(((hour - 9) / 3) ** 2))
    evening = 6_000 * math.exp(-(((hour - 19) / 2.5) ** 2))
    return base + morning + evening


def build_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = random.Random(SEED)
    start = datetime.now(UTC).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=DAYS)

    generation_rows: list[dict] = []
    price_rows: list[dict] = []
    weather_rows: list[dict] = []

    wind_level = 0.45  # slow random walk of the capacity factor

    for hour_offset in range(DAYS * 24):
        ts = start + timedelta(hours=hour_offset)
        hour = ts.hour
        is_weekend = ts.weekday() >= 5

        wind_level = min(0.95, max(0.03, wind_level + rng.uniform(-0.08, 0.08)))
        wind_onshore = 58_000 * wind_level
        wind_offshore = 8_500 * min(1.0, wind_level * 1.15)
        solar = _solar_mw(hour) * rng.uniform(0.6, 1.0)
        load = _load_mw(hour, is_weekend) * rng.uniform(0.97, 1.03)

        renewable = wind_onshore + wind_offshore + solar + 4_500
        residual = max(2_000.0, load - renewable)

        values = {
            "Solar": solar,
            "Wind onshore": wind_onshore,
            "Wind offshore": wind_offshore,
            "Biomass": 4_500.0,
            "Fossil gas": residual * 0.45,
            "Fossil hard coal": residual * 0.25,
            "Fossil brown coal / lignite": residual * 0.30,
            "Load": load,
        }

        # Four 15-minute intervals per hour, jittered around the hourly value.
        for quarter in range(4):
            q_ts = ts + timedelta(minutes=15 * quarter)
            for production_type, value in values.items():
                generation_rows.append(
                    {
                        "timestamp_utc": q_ts,
                        "production_type": production_type,
                        "value_mw": round(value * rng.uniform(0.98, 1.02), 2),
                    }
                )

        # Price falls as the renewable share rises, and can go negative.
        share = renewable / load
        price = 120 - 130 * share + rng.uniform(-15, 15)
        price_rows.append({"timestamp_utc": ts, "price_eur_mwh": round(price, 2)})

        weather_rows.append(
            {
                "timestamp_utc": ts,
                "temperature_c": round(8 + 6 * math.sin(hour / 24 * 2 * math.pi), 1),
                "wind_speed_100m_kmh": round(wind_level * 75, 1),
                "shortwave_radiation_wm2": round(_solar_mw(hour) / 45, 1),
                "cloud_cover_pct": rng.randint(0, 100),
            }
        )

    now = pd.Timestamp.now(tz="UTC")
    frames = []
    for rows in (generation_rows, price_rows, weather_rows):
        frame = pd.DataFrame(rows)
        frame["ingested_at_utc"] = now
        frames.append(frame)

    return frames[0], frames[1], frames[2]


def main() -> None:
    settings = load_settings()
    engine = get_engine(settings)
    ensure_schema(engine, settings.raw_schema)

    generation, prices, weather = build_frames()
    load_frame(engine, generation, "generation", settings.raw_schema)
    load_frame(engine, prices, "day_ahead_prices", settings.raw_schema)
    load_frame(engine, weather, "weather", settings.raw_schema)

    print(
        f"Seeded {len(generation):,} generation rows, {len(prices):,} price rows, "
        f"{len(weather):,} weather rows."
    )


if __name__ == "__main__":
    main()
