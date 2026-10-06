.PHONY: install dev-api dev-web test lint typecheck

install:
	python -m pip install -e ".[dev]"
	npm install

dev-api:
	python -m uvicorn apps.api.app.main:app --reload --host 127.0.0.1 --port 8000

dev-web:
	npm run dev:web

test:
	python -m pytest
	npm run test:web

lint:
	python -m ruff check .
	npm run lint:web

typecheck:
	python -m mypy apps packages
	npm --workspace apps/web run typecheck
