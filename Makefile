# Makefile

venv:
	source .venv/bin/activate

run:
	bash scripts/dev_run.sh

test:
	PYTHONPATH=. pytest -q

test-cov:
	PYTHONPATH=. pytest -q --cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=80

deps-compile:
	python -m pip install --upgrade pip pip-tools
	pip-compile --resolver=backtracking --upgrade --strip-extras --output-file=requirements.txt requirements.in

deps-sync:
	python -m pip install --upgrade pip pip-tools
	pip-sync requirements.txt

audit:
	bandit -q -r app -x tests,migrations
	pip-audit -r requirements.txt --progress-spinner=off

seed:
	PYTHONPATH=. python scripts/seed.py

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
