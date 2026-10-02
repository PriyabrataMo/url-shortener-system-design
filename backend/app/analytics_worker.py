from __future__ import annotations

import os
import socket
import time
from collections import Counter

from psycopg_pool import ConnectionPool
from redis import Redis
from redis.exceptions import ResponseError


DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL = os.environ["REDIS_URL"]
STREAM = os.environ.get("CLICK_STREAM", "click-events")
GROUP = os.environ.get("CLICK_CONSUMER_GROUP", "analytics-workers")
CONSUMER = os.environ.get("CLICK_CONSUMER", socket.gethostname())
BATCH_SIZE = int(os.environ.get("CLICK_BATCH_SIZE", "500"))


def ensure_consumer_group(redis: Redis) -> None:
    try:
        redis.xgroup_create(STREAM, GROUP, id="0-0", mkstream=True)
    except ResponseError as error:
        if "BUSYGROUP" not in str(error):
            raise


def read_messages(redis: Redis, message_id: str):
    return redis.xreadgroup(
        GROUP,
        CONSUMER,
        {STREAM: message_id},
        count=BATCH_SIZE,
        block=5000 if message_id == ">" else None,
    )


def flatten_messages(response) -> list[tuple[str, dict[str, str]]]:
    messages = []
    for _stream_name, entries in response:
        messages.extend(entries)
    return messages


def record_batch(pool: ConnectionPool, redis: Redis, messages) -> None:
    counts = Counter(fields["code"] for _message_id, fields in messages)
    with pool.connection() as db:
        for code, count in counts.items():
            db.execute(
                "UPDATE url_mappings SET clicks = clicks + %s WHERE code = %s",
                (count, code),
            )
        db.commit()

    redis.xack(STREAM, GROUP, *(message_id for message_id, _fields in messages))


def recover_pending(redis: Redis, pool: ConnectionPool) -> None:
    while True:
        messages = flatten_messages(read_messages(redis, "0"))
        if not messages:
            return
        record_batch(pool, redis, messages)


def main() -> None:
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    pool = ConnectionPool(conninfo=DATABASE_URL, min_size=1, max_size=2)
    ensure_consumer_group(redis)
    recover_pending(redis, pool)

    print(
        f"analytics worker started stream={STREAM} group={GROUP} consumer={CONSUMER}",
        flush=True,
    )
    while True:
        messages = flatten_messages(read_messages(redis, ">"))
        if messages:
            record_batch(pool, redis, messages)
        else:
            time.sleep(0.1)


if __name__ == "__main__":
    main()
