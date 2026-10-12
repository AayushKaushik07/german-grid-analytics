-- NOT an init script. Run this AFTER the first load, once the tables exist:
--   make index
-- or:
--   docker compose exec -T postgres psql -U $POSTGRES_USER -d $POSTGRES_DB < sql/maintenance/indexes.sql
--
-- Without these, the delete-then-insert step in loaders.py degrades into a
-- sequential scan as the tables grow past a few million rows.

CREATE INDEX IF NOT EXISTS idx_generation_ts   ON raw.generation (timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_generation_type ON raw.generation (production_type);
CREATE INDEX IF NOT EXISTS idx_prices_ts       ON raw.day_ahead_prices (timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_weather_ts      ON raw.weather (timestamp_utc);
