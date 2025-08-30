# Makefile

venv:
	source .venv/bin/activate

run:
	bash scripts/dev_run.sh

test:
	PYTHONPATH=. pytest -q

migrate:
	alembic revision --autogenerate -m "$(m)"

upgrade:
	alembic upgrade head

downgrade:
	alembic downgrade -1

# Convenience alias to apply latest migrations
db-up:
	alembic upgrade head

# --- Code quality ---

lint:
	ruff check . && black --check .

format:
	ruff check --fix . && black .

type-check:
	mypy .

precommit-install:
	pre-commit install

precommit-run:
	pre-commit run --all-files
