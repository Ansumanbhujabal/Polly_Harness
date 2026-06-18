.PHONY: install lint typecheck test test-unit test-integration eval seed run docker-build docker-up docker-down clean

install:
	uv venv && uv pip install -e ".[dev]"

lint:
	uv run ruff check app tests
	uv run ruff format --check app tests

format:
	uv run ruff format app tests
	uv run ruff check --fix app tests

typecheck:
	uv run mypy app

test:
	uv run pytest

test-unit:
	uv run pytest -m unit

test-integration:
	uv run pytest -m integration

eval:
	uv run python -m eval.run_suite

seed:
	uv run python -m data.seed.seed_qdrant
	uv run python -m data.seed.seed_state

run:
	uv run python -m app.main

docker-build:
	docker build -t refund-harness:latest .

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

clean:
	rm -rf .venv .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov data/state.db*
	find . -type d -name __pycache__ -exec rm -rf {} +
