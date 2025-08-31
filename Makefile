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

screenshots:
	# Ensure playwright is installed and browsers are available:
	#   pip install -r requirements.txt && make playwright-install
	PYTHONPATH=. python scripts/screenshots.py

playwright-install:
	# Install Playwright browsers (Chromium)
	python -m playwright install chromium

playwright-install-deps:
	# Linux-only: install system deps for headless Chromium (requires sudo)
	# Run: sudo playwright install-deps chromium
	@echo "Run with sudo (outside make): 'sudo playwright install-deps chromium'"

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
