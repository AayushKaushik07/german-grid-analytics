"""CLI entrypoint for the extract-and-load step.

Examples
--------
Backfill two years::

    python -m ingestion.run_ingest --start 2024-01-01 --end 2025-12-31

Daily incremental (yesterday, the default)::

    python -m ingestion.run_ingest
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta

from sqlalchemy import Engine

from ingestion import api_clients, transform
from ingestion.config import Settings, load_settings
from ingestion.loaders import ensure_schema, get_engine, load_frame

log = logging.getLogger("ingest")

# The APIs are happy with long ranges, so chunk generously: fewer, larger
# requests are both faster and far less likely to trip the rate limiter than
# many small ones. Chunking at all still keeps memory flat and makes a partial
# failure cheap to resume from.
CHUNK_DAYS = 90


def _date_chunks(start: date, end: date, size: int = CHUNK_DAYS):
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=size - 1), end)
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(days=1)


def load_window(
    engine: Engine,
    settings: Settings,
    chunk_start: date,
    chunk_end: date,
    country: str,
    bidding_zone: str,
) -> int:
    """Extract, transform and load one date window. Returns rows written."""
    written = 0

    generation = transform.add_ingested_at(
        transform.parse_public_power(
            api_clients.fetch_public_power(chunk_start, chunk_end, country)
        )
    )
    written += load_frame(engine, generation, "generation", settings.raw_schema)

    prices = transform.add_ingested_at(
        transform.parse_prices(
            api_clients.fetch_day_ahead_prices(chunk_start, chunk_end, bidding_zone)
        )
    )
    written += load_frame(engine, prices, "day_ahead_prices", settings.raw_schema)

    weather = transform.add_ingested_at(
        transform.parse_weather(api_clients.fetch_weather(chunk_start, chunk_end))
    )
    written += load_frame(engine, weather, "weather", settings.raw_schema)

    return written


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    yesterday = date.today() - timedelta(days=1)
    parser = argparse.ArgumentParser(description="Extract and load German grid data.")
    parser.add_argument("--start", type=date.fromisoformat, default=yesterday)
    parser.add_argument("--end", type=date.fromisoformat, default=yesterday)
    parser.add_argument("--country", default="de")
    parser.add_argument("--bidding-zone", default="DE-LU")
    parser.add_argument("--verbose", action="store_true", help="DEBUG-level logging.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
    )

    if args.start > args.end:
        log.error("--start must not be after --end")
        return 1

    settings = load_settings()
    engine = get_engine(settings)
    ensure_schema(engine, settings.raw_schema)

    total = 0
    for chunk_start, chunk_end in _date_chunks(args.start, args.end):
        log.info("=== Window %s -> %s ===", chunk_start, chunk_end)
        try:
            total += load_window(
                engine,
                settings,
                chunk_start,
                chunk_end,
                args.country,
                args.bidding_zone,
            )
        except Exception:
            # Loads are idempotent, so everything before this window is safely
            # in place. Tell the operator exactly how to pick up where we left
            # off rather than making them work it out from the traceback.
            log.error(
                "Window %s -> %s failed after %s rows. Earlier windows are "
                "already loaded -- resume with: --start %s --end %s",
                chunk_start,
                chunk_end,
                total,
                chunk_start,
                args.end,
            )
            raise

    log.info("Done. %s rows written in total.", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
