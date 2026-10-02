.PHONY: install dev run production test

HOST ?= 127.0.0.1
PORT ?= 8000
UV_CACHE_DIR ?= .uv-cache
export UV_CACHE_DIR

install:
	uv sync

# Development server with automatic reload when Python files change.
dev:
	uv run gunicorn --reload --workers 1 --bind $(HOST):$(PORT) --access-logfile - --error-logfile - "app:create_app()"

run: dev

# Production-style server: no auto-reload and multiple worker processes.
production:
	uv run gunicorn --workers 2 --bind 0.0.0.0:$(PORT) --access-logfile - --error-logfile - "app:create_app()"

test:
	uv run pytest
