.PHONY: install dev run test lint format typecheck up down logs clean

install:
	pip install -e ".[dev]"

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2

test:
	pytest -v

lint:
	ruff check app tests

format:
	black app tests
	ruff check --fix app tests

typecheck:
	mypy app

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f api

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache *.egg-info
