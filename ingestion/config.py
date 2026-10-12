"""Configuration resolved from environment variables (12-factor style)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    pg_host: str
    pg_port: int
    pg_database: str
    pg_user: str
    pg_password: str
    raw_schema: str = "raw"

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.pg_user}:{self.pg_password}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_database}"
        )


def load_settings() -> Settings:
    """Read settings from the environment. Fails loudly if a secret is missing."""
    try:
        return Settings(
            pg_host=os.environ.get("POSTGRES_HOST", "localhost"),
            pg_port=int(os.environ.get("POSTGRES_PORT", "5432")),
            pg_database=os.environ["POSTGRES_DB"],
            pg_user=os.environ["POSTGRES_USER"],
            pg_password=os.environ["POSTGRES_PASSWORD"],
            raw_schema=os.environ.get("RAW_SCHEMA", "raw"),
        )
    except KeyError as exc:
        raise RuntimeError(
            f"Missing required environment variable: {exc.args[0]}. "
            "Copy .env.example to .env and fill it in."
        ) from exc
