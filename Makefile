.PHONY: help up down ingest backfill dbt docs index test lint fresh psql

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up:  ## Start Postgres
	docker compose up -d postgres

down:  ## Stop everything (data volume survives)
	docker compose down

ingest:  ## Load yesterday
	docker compose run --rm pipeline python -m ingestion.run_ingest

backfill:  ## Load a range: make backfill START=2024-01-01 END=2025-12-31
	docker compose run --rm pipeline python -m ingestion.run_ingest \
		--start $(START) --end $(END)

dbt:  ## Build all dbt models and run tests
	docker compose run --rm -w /app/dbt pipeline dbt build

docs:  ## Serve the dbt docs site on localhost:8080
	docker compose run --rm -p 8080:8080 -w /app/dbt pipeline \
		sh -c "dbt docs generate && dbt docs serve --port 8080 --host 0.0.0.0"

index:  ## Create raw-table indexes (run once, after the first load)
	docker compose exec -T postgres psql -U $${POSTGRES_USER} -d $${POSTGRES_DB} \
		< sql/maintenance/indexes.sql

test:  ## Run the Python unit tests
	pytest -q

lint:  ## Lint and format-check
	ruff check .
	ruff format --check .

psql:  ## Open a psql shell
	docker compose exec postgres psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}

fresh: down up  ## Rebuild from scratch, last 90 days
	sleep 5
	$(MAKE) backfill START=$$(date -d '90 days ago' +%Y-%m-%d) END=$$(date -d 'yesterday' +%Y-%m-%d)
	$(MAKE) index
	$(MAKE) dbt
