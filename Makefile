# Makefile

venv:
	source .venv/bin/activate

run:
	uvicorn app.main:app --reload

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
