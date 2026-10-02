from __future__ import annotations

import random
import secrets
import string
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, redirect, request
from psycopg.errors import UniqueViolation

from .db import get_db

api = Blueprint("api", __name__)
ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 7
NOT_FOUND_MARKER = "1"
RELEASE_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


def get_redis():
    return current_app.extensions["redis"]


def get_local_cache():
    return current_app.extensions["local_cache"]


def is_valid_url(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 2048:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def new_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def url_cache_key(code: str) -> str:
    return f"url:{code}"


def missing_cache_key(code: str) -> str:
    return f"missing:{code}"


def lock_key(code: str) -> str:
    return f"lock:url:{code}"


def cache_ttl() -> int:
    base = current_app.config["CACHE_TTL_SECONDS"]
    jitter = current_app.config["CACHE_TTL_JITTER_SECONDS"]
    return base + random.randint(0, jitter) if jitter else base


def cache_url(code: str, long_url: str) -> None:
    get_redis().setex(url_cache_key(code), cache_ttl(), long_url)
    get_local_cache().set(code, long_url)


def release_lock(key: str, token: str) -> None:
    get_redis().eval(RELEASE_LOCK_SCRIPT, 1, key, token)


def read_cached_url(code: str) -> str | None:
    local_value = get_local_cache().get(code)
    if isinstance(local_value, str):
        return local_value

    redis_value = get_redis().get(url_cache_key(code))
    if isinstance(redis_value, str):
        get_local_cache().set(code, redis_value)
        return redis_value
    return None


def read_missing_marker(code: str) -> bool:
    return get_redis().get(missing_cache_key(code)) == NOT_FOUND_MARKER


def load_url_with_single_flight(code: str) -> str | None:
    cached = read_cached_url(code)
    if cached is not None:
        return cached
    if read_missing_marker(code):
        return None

    redis = get_redis()
    key = lock_key(code)
    token = str(uuid4())
    acquired = bool(
        redis.set(
            key,
            token,
            nx=True,
            ex=current_app.config["CACHE_LOCK_TTL_SECONDS"],
        )
    )

    if acquired:
        try:
            cached = read_cached_url(code)
            if cached is not None:
                return cached

            row = get_db().execute(
                "SELECT long_url FROM url_mappings WHERE code = %s",
                (code,),
            ).fetchone()
            if row is None:
                redis.setex(
                    missing_cache_key(code),
                    current_app.config["NEGATIVE_CACHE_TTL_SECONDS"],
                    NOT_FOUND_MARKER,
                )
                return None

            long_url = row["long_url"]
            cache_url(code, long_url)
            return long_url
        finally:
            release_lock(key, token)

    for _ in range(current_app.config["CACHE_LOCK_RETRIES"]):
        time.sleep(current_app.config["CACHE_LOCK_RETRY_DELAY_SECONDS"])
        cached = read_cached_url(code)
        if cached is not None:
            return cached
        if read_missing_marker(code):
            return None

    # The lock holder may have crashed. Make one authoritative lookup rather than waiting forever.
    row = get_db().execute(
        "SELECT long_url FROM url_mappings WHERE code = %s",
        (code,),
    ).fetchone()
    if row is None:
        redis.setex(
            missing_cache_key(code),
            current_app.config["NEGATIVE_CACHE_TTL_SECONDS"],
            NOT_FOUND_MARKER,
        )
        return None
    long_url = row["long_url"]
    cache_url(code, long_url)
    return long_url


def publish_click(code: str) -> None:
    get_redis().xadd(
        current_app.config["CLICK_STREAM"],
        {
            "event_id": str(uuid4()),
            "code": code,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "status_code": "302",
        },
        maxlen=current_app.config["CLICK_STREAM_MAXLEN"],
        approximate=True,
    )


@api.post("/api/urls")
def create_url():
    payload = request.get_json(silent=True) or {}
    long_url = payload.get("long_url")
    if not is_valid_url(long_url):
        return jsonify({"error": "long_url must be a valid http or https URL"}), 400

    db = get_db()
    for _ in range(5):
        code = new_code()
        try:
            db.execute(
                "INSERT INTO url_mappings (code, long_url) VALUES (%s, %s)",
                (code, long_url),
            )
            db.commit()
            cache_url(code, long_url)
            return (
                jsonify(
                    {
                        "code": code,
                        "long_url": long_url,
                        "short_url": f"{current_app.config['SHORT_URL_BASE']}/{code}",
                    }
                ),
                201,
            )
        except UniqueViolation:
            db.rollback()

    return jsonify({"error": "could not generate a unique short code"}), 503


@api.get("/api/urls/<code>")
def get_url(code: str):
    row = get_db().execute(
        "SELECT code, long_url, created_at, clicks FROM url_mappings WHERE code = %s",
        (code,),
    ).fetchone()
    if row is None:
        return jsonify({"error": "short URL not found"}), 404
    return jsonify(dict(row))


@api.get("/r/<code>")
def redirect_to_long_url(code: str):
    long_url = load_url_with_single_flight(code)
    if long_url is None:
        return jsonify({"error": "short URL not found"}), 404

    publish_click(code)
    return redirect(long_url, code=302)
