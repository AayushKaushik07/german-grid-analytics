"""Load tidy DataFrames into the Postgres ``raw`` schema.

Loads are *idempotent by design*: for each target table we delete the rows in
the ingested time window and insert the new ones in the same transaction.
Re-running the same day therefore replaces rather than duplicates, and a load
that fails half-way rolls back completely instead of leaving the window empty,
which is what makes a daily incremental job safe to retry after a failure.
"""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import Engine, create_engine, text

from ingestion.config import Settings

log = logging.getLogger(__name__)


def get_engine(settings: Settings) -> Engine:
    return create_engine(settings.sqlalchemy_url, pool_pre_ping=True)


def ensure_schema(engine: Engine, schema: str) -> None:
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))


def load_frame(
    engine: Engine,
    frame: pd.DataFrame,
    table: str,
    schema: str,
    timestamp_column: str = "timestamp_utc",
) -> int:
    """Atomically delete-then-insert the window covered by ``frame``; returns rows."""
    if frame.empty:
        log.warning("Nothing to load into %s.%s -- empty frame", schema, table)
        return 0

    window_start = frame[timestamp_column].min()
    window_end = frame[timestamp_column].max()

    with engine.begin() as conn:
        table_exists = conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = :schema AND table_name = :table"
            ),
            {"schema": schema, "table": table},
        ).first()

        if table_exists:
            deleted = conn.execute(
                text(
                    f'DELETE FROM "{schema}"."{table}" '
                    f"WHERE {timestamp_column} BETWEEN :start AND :end"
                ),
                {"start": window_start, "end": window_end},
            ).rowcount
            log.info("Removed %s existing rows from %s.%s", deleted, schema, table)

        # Same connection, same transaction as the delete: either both happen
        # or neither does.
        frame.to_sql(
            table,
            conn,
            schema=schema,
            if_exists="append",
            index=False,
            chunksize=10_000,
            method="multi",
        )
    log.info("Loaded %s rows into %s.%s", len(frame), schema, table)
    return len(frame)
