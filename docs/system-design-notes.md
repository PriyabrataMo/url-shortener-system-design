# URL Shortener: Interview Notes

## 1. Requirements to clarify

Functional requirements:

- Create a short URL for a valid `http` or `https` destination.
- Redirect a short code to its destination.
- Decide whether URLs expire, can be deleted, or can be edited.
- Decide whether users can choose custom aliases.
- Define whether click analytics are required and how fresh they must be.

Non-functional requirements:

- Redirect latency target, for example p95 below 100 ms at the service layer.
- Availability target for redirects, which is usually higher than the create path.
- Expected create rate, redirect rate, peak multiplier, retention, and regions.
- Abuse controls: rate limits, authentication, domain policy, and malware scanning.

## 2. Example capacity estimate

Assume 10 million URL creations and 1 billion redirects per month:

```text
Creates:   10,000,000 / month  ≈ 4 writes/second average
Redirects: 1,000,000,000/month ≈ 386 reads/second average
10x peak:                         ≈ 3,860 reads/second
```

The time window matters. Always ask whether the numbers are per month, day, or second, then plan for a peak multiplier rather than the average alone.

## 3. Data model

```sql
url_mappings(
  code        text primary key,
  long_url    text not null,
  created_at  timestamp not null,
  clicks      bigint not null default 0
)
```

The primary key makes collisions safe. Random Base62 generation is convenient, but the database uniqueness constraint is the final authority. On a collision, generate another code and retry. At larger scale, allocate a unique numeric or Snowflake-style ID and encode it as Base62.

## 4. Request paths

### Create

```text
Client -> API -> validate URL -> allocate code -> PostgreSQL commit
                                      |
                                      +--> warm Redis and local cache
```

The mapping is durable before the API returns `201`.

### Redirect

```text
Client -> edge/load balancer -> stateless redirect service
                                  |
                                  +--> local cache
                                  +--> Redis cache
                                  +--> PostgreSQL on miss
                                  +--> Redis Stream click event
                                  +--> 302 response
```

The common case should not query PostgreSQL. Click analytics are asynchronous so a slow analytics database cannot block redirects.

## 5. Cache and hot-key strategy

- Local process cache: bounded LRU, short TTL, protects Redis from very hot keys.
- Redis cache: shared cache across backend replicas, longer TTL, and TTL jitter to avoid synchronized expiry.
- Negative caching: store a short-lived marker for missing codes to protect PostgreSQL from repeated invalid requests.
- Single-flight: acquire `SET lock:<code> value NX EX seconds`; one request loads the mapping while waiters retry the cache.
- Hot-key replication: in a multi-node production cache, replicate exceptionally hot entries or serve them from edge/local caches. The local project demonstrates the first layer but has only one Redis instance.
- Immutable mappings simplify invalidation. If destinations can change, define cache invalidation or versioning before choosing long cache TTLs.

## 6. Click analytics

The redirect service publishes an event such as:

```json
{
  "event_id": "unique-id",
  "code": "aB91xK",
  "occurred_at": "2026-01-01T00:00:00Z",
  "status_code": 302
}
```

The worker reads events in batches, aggregates by code and time window, and writes to an analytics store. Redis Streams are used here to keep the lab small. Kafka, Kinesis, Pub/Sub, or SQS are stronger production choices depending on replay, throughput, and operational requirements.

The dashboard is eventually consistent. State a freshness objective, such as “99% of clicks visible within 10 seconds.” Consumer groups and acknowledgements provide at-least-once delivery; production counters need event-ID deduplication to avoid double counting after a worker crash.

## 7. Storage and availability evolution

Prototype:

- One PostgreSQL primary
- One Redis instance
- Multiple stateless backend replicas
- Nginx gateway

Production discussion:

- Multi-AZ PostgreSQL with backups and tested restores
- Read replicas for mapping reads, with primary routing after a create when read-after-write consistency is required
- Connection-pool limits to prevent replicas from overwhelming PostgreSQL
- Redis replication and failover, then sharding when memory or throughput requires it
- Partitioning or sharding mappings by a hash of the short code at very large size
- CDN or edge caching for immutable redirects
- Global routing and regional failover

### MongoDB replication timing

If MongoDB is selected instead of PostgreSQL, writes normally go to the primary of a replica set. The primary updates its data, records an operation in the oplog, and secondaries continuously read and apply those oplog operations locally. A secondary does not copy the entire database after every write.

```text
Client write
    ↓
Replica-set primary updates data and oplog
    ↓
Secondaries read the oplog
    ↓
Each secondary updates its own data and indexes
```

With `w: 1`, the primary can acknowledge before secondaries finish applying the operation. With `w: "majority"`, MongoDB waits for acknowledgement from a majority of voting data-bearing members. The stronger write concern improves durability but can increase write latency.

When a new secondary joins, it performs an initial sync of the existing data, builds indexes, and then applies newer oplog entries until it catches up. The time between the primary and a secondary is replication lag.

For a URL shortener, replica lag creates a read-after-write question: a user may create a URL and immediately follow it before a secondary has applied the mapping. Route that first read to the primary or serve it from the cache warmed after creation. Later redirect reads can use replicas if the application accepts a small amount of eventual consistency.

Useful operational checks include:

```javascript
rs.status()
rs.printSecondaryReplicationInfo()
```

The interview explanation is: “The primary accepts the write and publishes it through the oplog. Secondaries replay the operation asynchronously. I choose `w: \"majority\"` when the write must survive a primary failure, monitor replication lag, and route read-after-write traffic to the primary or cache.”

## 8. HTTP redirect trade-off

- `302`: temporary redirect; common default while destinations may change.
- `307`: temporary redirect while preserving the HTTP method.
- `301`: permanent redirect; browsers and intermediaries may cache it aggressively.
- `308`: permanent redirect while preserving the HTTP method.

Use permanent redirects only when the destination is genuinely immutable or the cache behavior is explicitly acceptable.

## 9. Observability and experiments

Measure:

- Request rate, error rate, and p50/p95/p99 latency
- Local-cache hit rate and Redis hit rate
- PostgreSQL query latency and pool saturation
- Redis memory, command latency, stream length, pending messages, and worker lag
- Click freshness and duplicate-event rate
- Container CPU, memory, network I/O, and restarts

Run load tests gradually. A `137` exit from the k6 container means the generator was killed, usually by its memory limit; it does not prove that the backend failed. Compare client-side results with gateway, backend, Redis, and PostgreSQL metrics.

## 10. Interview closing summary

“I would keep URL creation strongly durable in a relational mapping store, make the redirect service stateless, serve hot mappings from local and distributed caches, protect misses with negative caching and single-flight locks, and move analytics to an asynchronous stream. I would scale PostgreSQL reads with replicas first, then partition or shard when required, while adding multi-AZ failover, backups, rate limiting, abuse protection, and observability.”

## 11. Further reading

- [MongoDB replica-set oplog](https://www.mongodb.com/docs/manual/core/replica-set-oplog/)
- [MongoDB write concern](https://www.mongodb.com/docs/manual/reference/write-concern/)
- [MongoDB sharding](https://www.mongodb.com/docs/manual/sharding/)
- [MongoDB WiredTiger storage engine](https://www.mongodb.com/docs/manual/core/wiredtiger/)
