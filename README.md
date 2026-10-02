# URL Shortener — System Design Interview Lab

A deliberately small URL-shortener implementation for practicing a system-design interview from requirements through scale trade-offs.

The code is a learning reference, not a production-ready public service. It demonstrates the request path, caching, asynchronous click analytics, container limits, scaling experiments, and the failure modes worth discussing in an interview.

## Architecture

```text
Browser
  |
  v
Next.js UI :3000
  |
  v
Nginx gateway :8000
  |
  v
Flask/Gunicorn backend replicas
  |                    |
  v                    v
Redis cache       PostgreSQL mappings
  |
  +--> Redis Stream --> analytics-worker --> PostgreSQL click aggregate
```

### Redirect path

1. The backend checks its process-local LRU cache.
2. On a miss, it checks Redis.
3. A Redis `SET NX EX` lock prevents a cache stampede for the same code.
4. The lock holder reads PostgreSQL and fills Redis plus the local cache.
5. Missing codes receive a short-lived negative-cache entry.
6. The backend publishes a click event and returns `302`.
7. `analytics-worker` batches events and updates the click counter asynchronously.

The redirect does not wait for analytics. Therefore the click dashboard is eventually consistent by design.

## Technology choices

- Flask and Gunicorn for the API
- PostgreSQL for durable URL mappings
- Redis for redirect caching, distributed locking, negative caching, and the learning event stream
- Nginx as the local gateway and load-balancing layer
- Next.js, Bun, and small shadcn-style components for the UI
- Docker Compose for repeatable local experiments
- k6 for load testing
- uv for Python dependency management

## Run locally

Requirements: Docker Desktop.

```bash
cp .env.example .env
docker compose up --build -d
open http://localhost:3000
curl http://localhost:8000/health
```

The default local configuration uses only localhost values. The `.env` file is ignored by Git.

Create a URL directly:

```bash
curl -X POST http://localhost:8000/api/urls \
  -H 'Content-Type: application/json' \
  -d '{"long_url":"https://example.com/system-design"}'
```

## Scale the backend and load test

```bash
docker compose up --build -d --scale backend=3
make load VUS=10 DURATION=30s
```

The public profile is optional. Configure `PUBLIC_API_URL`, `SHORT_URL_BASE`, and `ALLOWED_ORIGINS` in your local `.env`, then configure your own tunnel provider separately. Never commit tunnel credentials.

```bash
make load-public VUS=10 DURATION=30s
```

Increase traffic gradually and observe latency, failure rate, CPU, memory, PostgreSQL size, Redis state, and analytics lag. A load-generator failure is not automatically an application failure; always inspect which container stopped or exceeded its limit.

## Interview discussion guide

Start an interview answer in this order:

1. Clarify requirements: create URLs, redirect URLs, expiration, custom aliases, ownership, analytics, and deletion.
2. Define scale: creates per second, redirects per second, peak multiplier, retention, availability, and latency targets.
3. Estimate storage and traffic before choosing infrastructure.
4. Design the core mapping: short code to long URL, unique constraint, and collision retry behavior.
5. Separate the write path from the hot read path.
6. Add cache-aside reads, TTLs, negative caching, single-flight locking, and hot-key protection.
7. Move click analytics off the redirect critical path.
8. Explain replication, failover, backups, rate limits, abuse protection, observability, and regional behavior.
9. Name the trade-offs: `302`/`307` versus cacheable `301`/`308`, strong versus eventual consistency, and PostgreSQL versus a distributed key-value store.

The detailed reasoning and open production gaps are in [`docs/system-design-notes.md`](docs/system-design-notes.md). Operational commands are in [`COMMANDS.md`](COMMANDS.md).

## Project structure

```text
url-shortener-app/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── analytics_worker.py
│   │   ├── cache.py
│   │   ├── db.py
│   │   └── routes.py
│   ├── tests/
│   └── pyproject.toml
├── docs/
│   └── system-design-notes.md
├── frontend/
├── infra/nginx.conf
├── load-tests/redirect.js
├── compose.yaml
└── Makefile
```

## Limitations intentionally left for interview discussion

- One PostgreSQL instance and one Redis instance are used locally.
- Redis Streams provide a simple learning queue; production event volume may require Kafka, Kinesis, or Pub/Sub.
- The worker is at-least-once. Production analytics must deduplicate event IDs before counting.
- No authentication, rate limiting, malware scanning, custom aliases, deletion, or retention jobs are implemented.
- Random Base62 generation relies on a database uniqueness constraint and bounded retries. A large system may encode allocated sequence or Snowflake-style IDs.
- The local Docker memory limits are for experiments, not capacity planning.
