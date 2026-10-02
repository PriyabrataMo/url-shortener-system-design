# URL Shortener Lab Commands

Run these commands from this directory:

```bash
cd path/to/url-shortener-app
```

## Start and stop

```bash
# Start local development stack
make up

# Start the public stack in the background
docker compose --profile public up --build --scale frontend=1 --scale backend=3 -d

# Stop containers
make down

# Stop containers and delete the PostgreSQL volume
# Destructive: deletes database data.
make reset
```

## Containers and logs

```bash
# List containers
docker compose ps

# Follow backend logs, including all replicas
docker compose logs -f --tail=100 backend

# Follow gateway logs
docker compose logs -f --tail=100 gateway

# Follow Cloudflare Tunnel logs
docker compose --profile public logs -f --tail=100 cloudflared

# Inspect one container by ID
docker logs -f --tail=100 CONTAINER_ID
```

## CPU and memory

```bash
# Real-time resource usage
docker stats

# One snapshot with useful columns
docker stats --no-stream \
  --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}"

# Compose services only
docker compose stats
```

`MEM USAGE / LIMIT` shows current memory versus the configured 512 MB limit. `NET I/O` and `BLOCK I/O` are cumulative since container start.

## PostgreSQL

```bash
# Open a PostgreSQL shell
docker compose exec postgres psql -U urlshortener -d urlshortener
```

Inside `psql`:

```sql
\dt
SELECT * FROM url_mappings;
SELECT COUNT(*) FROM url_mappings;
SELECT code, long_url, clicks, created_at
FROM url_mappings
ORDER BY created_at DESC
LIMIT 20;
\q
```

One-off database checks:

```bash
docker compose exec -T postgres psql -U urlshortener -d urlshortener \
  -c "SELECT COUNT(*) AS total_rows FROM url_mappings;"

docker compose exec -T postgres psql -U urlshortener -d urlshortener \
  -c "SELECT pg_size_pretty(pg_database_size(current_database())) AS database_size;"

docker compose exec postgres du -sh /var/lib/postgresql/data
```

## Asynchronous click analytics

Redirects do not update PostgreSQL synchronously. The API writes a small click event to a Redis Stream, returns the redirect, and `analytics-worker` batches the events into `url_mappings.clicks`.

```bash
# Follow the worker and API logs
docker compose logs -f --tail=100 analytics-worker backend

# Stream length and consumer-group state
docker compose exec -T redis redis-cli XLEN click-events
docker compose exec -T redis redis-cli XPENDING click-events analytics-workers

# Inspect the click counter after a redirect
docker compose exec -T postgres psql -U urlshortener -d urlshortener \
  -c "SELECT code, clicks FROM url_mappings ORDER BY created_at DESC LIMIT 10;"
```

The dashboard is intentionally eventually consistent: it may lag by one worker batch. Redis Streams retain the events (up to the configured approximate limit), while the consumer group tracks which events have been acknowledged.

## Clean test data

```bash
# Destructive: deletes URL mappings and cached mappings, but keeps the schema and volume.
docker compose exec -T postgres psql -U urlshortener -d urlshortener \
  -c "TRUNCATE TABLE url_mappings;"

docker compose exec -T redis redis-cli -n 0 FLUSHDB
```

## Public load tests

The test creates one URL, then repeatedly tests its redirect endpoint without following the redirect.

```bash
# Recommended progression
make load-public VUS=10 DURATION=30s
make load-public VUS=25 DURATION=30s
make load-public VUS=50 DURATION=30s
```

The public test uses a separate `k6-public` Compose service with `1.1.1.1` and `8.8.8.8` because Docker's internal resolver may fail to resolve the public API hostname after DNS changes.

`VUS` means virtual users. `DURATION` controls test length. A nonzero Make exit code can mean the latency threshold was crossed even when `http_req_failed` is `0.00%`.

## Public endpoint checks

Use plain URLs in the terminal. Do not paste Markdown syntax such as `[https://...](https://...)`.

```bash
curl -4 -i https://shortener.example.com/
curl -4 -i https://api.shortener.example.com/health

dig +short A shortener.example.com @1.1.1.1
dig +short A api.shortener.example.com @1.1.1.1
```

## Local CORS preflight

```bash
curl -i -X OPTIONS http://localhost:8000/api/urls \
  -H 'Origin: https://shortener.example.com' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: content-type'
```

The response should include:

```text
Access-Control-Allow-Origin: https://shortener.example.com
```
