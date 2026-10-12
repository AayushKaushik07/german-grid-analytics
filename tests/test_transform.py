"""Unit tests for the parsing layer.

These run offline against fixture payloads shaped like the real API responses,
so CI never depends on an upstream service being available.
"""

from __future__ import annotations

import pandas as pd
import pytest

from ingestion import transform

# 2024-01-01T00:00:00Z, then +15min, +30min, +45min
TIMESTAMPS = [1704067200, 1704068100, 1704069000, 1704069900]

POWER_PAYLOAD = {
    "unix_seconds": TIMESTAMPS,
    "production_types": [
        {"name": "Solar", "data": [0.0, 0.0, 0.0, 0.0]},
        {"name": "Wind onshore", "data": [20000.0, 21000.0, 22000.0, 23000.0]},
        {"name": "Fossil gas", "data": [5000.0, 5100.0, 5200.0, 5300.0]},
        {"name": "Load", "data": [40000.0, 40100.0, 40200.0, 40300.0]},
    ],
}

PRICE_PAYLOAD = {
    "unix_seconds": TIMESTAMPS,
    "price": [30.5, -12.0, 0.0, 45.25],
    "unit": "EUR/MWh",
}

WEATHER_PAYLOAD = {
    "hourly": {
        "time": ["2024-01-01T00:00", "2024-01-01T01:00"],
        "temperature_2m": [3.4, 3.1],
        "wind_speed_100m": [36.0, 18.0],
        "shortwave_radiation": [0.0, 0.0],
        "cloud_cover": [100, 88],
    }
}


class TestParsePublicPower:
    def test_flattens_to_long_format(self):
        frame = transform.parse_public_power(POWER_PAYLOAD)
        assert list(frame.columns) == ["timestamp_utc", "production_type", "value_mw"]
        # 4 timestamps x 4 production types
        assert len(frame) == 16

    def test_timestamps_are_utc_aware(self):
        frame = transform.parse_public_power(POWER_PAYLOAD)
        assert str(frame["timestamp_utc"].dt.tz) == "UTC"
        assert frame["timestamp_utc"].min() == pd.Timestamp("2024-01-01T00:00:00Z")

    def test_rejects_misaligned_series(self):
        broken = {
            "unix_seconds": TIMESTAMPS,
            "production_types": [{"name": "Solar", "data": [1.0, 2.0]}],
        }
        with pytest.raises(ValueError, match="misaligned"):
            transform.parse_public_power(broken)

    def test_rejects_payload_missing_keys(self):
        with pytest.raises(ValueError, match="missing required keys"):
            transform.parse_public_power({"unix_seconds": TIMESTAMPS})

    def test_empty_production_types_returns_empty_frame(self):
        frame = transform.parse_public_power({"unix_seconds": [], "production_types": []})
        assert frame.empty
        assert "value_mw" in frame.columns

    def test_nulls_are_coerced_not_dropped(self):
        payload = {
            "unix_seconds": TIMESTAMPS,
            "production_types": [{"name": "Solar", "data": [1.0, None, 3.0, 4.0]}],
        }
        frame = transform.parse_public_power(payload)
        assert len(frame) == 4
        assert frame["value_mw"].isna().sum() == 1


class TestParsePrices:
    def test_preserves_negative_prices(self):
        frame = transform.parse_prices(PRICE_PAYLOAD)
        assert (frame["price_eur_mwh"] < 0).sum() == 1

    def test_rejects_misaligned_arrays(self):
        with pytest.raises(ValueError, match="misaligned"):
            transform.parse_prices({"unix_seconds": TIMESTAMPS, "price": [1.0]})


class TestParseWeather:
    def test_renames_and_orders_columns(self):
        frame = transform.parse_weather(WEATHER_PAYLOAD)
        assert list(frame.columns) == [
            "timestamp_utc",
            "temperature_c",
            "wind_speed_100m_kmh",
            "shortwave_radiation_wm2",
            "cloud_cover_pct",
        ]

    def test_timestamps_parsed_as_utc(self):
        frame = transform.parse_weather(WEATHER_PAYLOAD)
        assert frame["timestamp_utc"].iloc[0] == pd.Timestamp("2024-01-01T00:00:00Z")

    def test_rejects_payload_without_hourly(self):
        with pytest.raises(ValueError, match="hourly"):
            transform.parse_weather({"daily": {}})


def test_add_ingested_at_stamps_every_row():
    frame = transform.parse_prices(PRICE_PAYLOAD)
    stamped = transform.add_ingested_at(frame)
    assert stamped["ingested_at_utc"].notna().all()
    assert len(stamped) == len(frame)
