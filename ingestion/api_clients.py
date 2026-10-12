"""Thin HTTP clients for the two upstream sources.

Both APIs are public, keyless and CC-BY licensed:
  * Energy-Charts (Fraunhofer ISE) -- https://api.energy-charts.info
  * Open-Meteo ERA5 archive       -- https://archive-api.open-meteo.com

These functions only fetch. All reshaping lives in ``transform.py`` so that the
parsing logic stays pure and unit-testable without network access.

Rate limiting
-------------
Neither API requires a key, and neither publishes a formal quota, but both will
return HTTP 429 under sustained backfill traffic. Three measures keep this
client a good citizen:

* a minimum interval between requests, so a long backfill cannot burst
* honouring the ``Retry-After`` response header when the server sends one
* a much longer backoff for 429 specifically than for a transient error

A backfill is a one-off cost. Waiting to be let back in is far cheaper than a
half-loaded warehouse.
"""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any

import requests

log = logging.getLogger(__name__)

ENERGY_CHARTS_BASE = "https://api.energy-charts.info"
OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"

# Roughly the geographic centre of Germany. One representative point keeps the
# project simple; see docs/architecture.md for the limitation this introduces.
DE_CENTROID_LAT = 51.16
DE_CENTROID_LON = 10.45

DEFAULT_TIMEOUT = 60
MAX_RETRIES = 6

# Backoff for ordinary transient failures: 2s, 4s, 8s...
BASE_BACKOFF_SECONDS = 2

# Backoff for HTTP 429. Deliberately far more patient: 30s, 60s, 120s...
# capped so a stuck job fails in minutes rather than hours.
RATE_LIMIT_BACKOFF_SECONDS = 30
MAX_BACKOFF_SECONDS = 300

# Minimum gap between any two outbound requests, enforced process-wide.
MIN_REQUEST_INTERVAL_SECONDS = 1.5

_last_request_at = 0.0


def _throttle() -> None:
    """Space requests out so a backfill loop cannot burst against the API."""
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
        time.sleep(MIN_REQUEST_INTERVAL_SECONDS - elapsed)
    _last_request_at = time.monotonic()


def _retry_after_seconds(response: requests.Response) -> float | None:
    """Read the Retry-After header if the server sent one."""
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        # The header may also be an HTTP date. Not worth parsing here; fall
        # back to our own backoff schedule.
        return None


def _get(url: str, params: dict[str, Any]) -> dict[str, Any]:
    """GET with throttling and rate-limit-aware backoff. Raises on final failure."""
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        _throttle()
        try:
            response = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT)

            if response.status_code == 429:
                wait = _retry_after_seconds(response)
                if wait is None:
                    wait = min(
                        RATE_LIMIT_BACKOFF_SECONDS * (2**attempt), MAX_BACKOFF_SECONDS
                    )
                log.warning(
                    "Rate limited by %s (attempt %s/%s) -- backing off %.0fs",
                    url,
                    attempt + 1,
                    MAX_RETRIES,
                    wait,
                )
                last_error = requests.HTTPError("429 Too Many Requests")
                time.sleep(wait)
                continue

            response.raise_for_status()
            return response.json()

        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            wait = min(BASE_BACKOFF_SECONDS * (2**attempt), MAX_BACKOFF_SECONDS)
            log.warning(
                "Request to %s failed (attempt %s/%s): %s -- retrying in %.0fs",
                url,
                attempt + 1,
                MAX_RETRIES,
                exc,
                wait,
            )
            time.sleep(wait)

    raise RuntimeError(f"GET {url} failed after {MAX_RETRIES} attempts") from last_error


def fetch_public_power(start: date, end: date, country: str = "de") -> dict[str, Any]:
    """Generation and load by production type.

    Response shape::

        {"unix_seconds": [...], "production_types": [{"name": "Solar", "data": [...]}]}
    """
    log.info("Fetching public_power %s -> %s (%s)", start, end, country)
    return _get(
        f"{ENERGY_CHARTS_BASE}/public_power",
        {"country": country, "start": start.isoformat(), "end": end.isoformat()},
    )


def fetch_day_ahead_prices(start: date, end: date, bzn: str = "DE-LU") -> dict[str, Any]:
    """Day-ahead spot prices in EUR/MWh for a bidding zone.

    Response shape::

        {"unix_seconds": [...], "price": [...], "unit": "EUR/MWh"}
    """
    log.info("Fetching price %s -> %s (%s)", start, end, bzn)
    return _get(
        f"{ENERGY_CHARTS_BASE}/price",
        {"bzn": bzn, "start": start.isoformat(), "end": end.isoformat()},
    )


def fetch_weather(
    start: date,
    end: date,
    lat: float = DE_CENTROID_LAT,
    lon: float = DE_CENTROID_LON,
) -> dict[str, Any]:
    """Hourly ERA5 reanalysis weather for one point.

    Response shape::

        {"hourly": {"time": [...], "temperature_2m": [...], ...}}
    """
    log.info("Fetching weather %s -> %s (%s, %s)", start, end, lat, lon)
    return _get(
        OPEN_METEO_ARCHIVE,
        {
            "latitude": lat,
            "longitude": lon,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "hourly": "temperature_2m,wind_speed_100m,shortwave_radiation,cloud_cover",
            "timezone": "UTC",
        },
    )
