FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DBT_PROFILES_DIR=/app/dbt

WORKDIR /app

# System deps for psycopg2 are already covered by the binary wheel; curl is
# only kept for container-level healthchecks.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ingestion/ ./ingestion/
COPY dbt/ ./dbt/
COPY analysis/ ./analysis/

CMD ["python", "-m", "ingestion.run_ingest"]
