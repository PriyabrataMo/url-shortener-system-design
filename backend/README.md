# URL Shortener API

The normal experiment path is from the project root:

```bash
docker compose up --build
```

The container runs Gunicorn with two workers. The application requires `DATABASE_URL`, `REDIS_URL`, and `SHORT_URL_BASE`. Redirects publish click events to Redis Streams; the separate `analytics-worker` batches them into PostgreSQL.

For direct development outside Docker, start PostgreSQL and Redis first, export those three variables, then run:

```bash
uv sync
make dev
```

Run tests:

```bash
uv run pytest
```

The API tests cover URL creation, redirect behavior, and invalid input. The end-to-end analytics path can be checked from the project root with:

```bash
docker compose logs -f analytics-worker
docker compose exec -T redis redis-cli XPENDING click-events analytics-workers
```
