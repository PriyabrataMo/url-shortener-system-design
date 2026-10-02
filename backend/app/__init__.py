from __future__ import annotations

import os

from flask import Flask, request
from flask_cors import CORS
from redis import Redis

from .cache import LocalTTLCache
from .db import close_db, get_db, init_db
from .routes import api


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE_URL=os.environ.get("DATABASE_URL"),
        REDIS_URL=os.environ.get("REDIS_URL"),
        SHORT_URL_BASE=os.environ.get("SHORT_URL_BASE"),
        ALLOWED_ORIGINS=os.environ.get("ALLOWED_ORIGINS"),
        CACHE_TTL_SECONDS=3600,
        CACHE_TTL_JITTER_SECONDS=300,
        LOCAL_CACHE_MAX_ENTRIES=10000,
        LOCAL_CACHE_TTL_SECONDS=60,
        NEGATIVE_CACHE_TTL_SECONDS=10,
        CACHE_LOCK_TTL_SECONDS=5,
        CACHE_LOCK_RETRIES=20,
        CACHE_LOCK_RETRY_DELAY_SECONDS=0.025,
        CLICK_STREAM="click-events",
        CLICK_STREAM_MAXLEN=1000000,
        CLICK_CONSUMER_GROUP="analytics-workers",
        CLICK_BATCH_SIZE=500,
    )

    if test_config:
        app.config.update(test_config)

    missing_config = [
        key
        for key in ("DATABASE_URL", "REDIS_URL", "SHORT_URL_BASE", "ALLOWED_ORIGINS")
        if not app.config[key]
    ]
    if missing_config:
        raise RuntimeError(f"Missing required configuration: {', '.join(missing_config)}")

    init_db(app)
    app.extensions["redis"] = Redis.from_url(app.config["REDIS_URL"], decode_responses=True)
    app.extensions["local_cache"] = LocalTTLCache(
        max_entries=app.config["LOCAL_CACHE_MAX_ENTRIES"],
        ttl_seconds=app.config["LOCAL_CACHE_TTL_SECONDS"],
    )

    # Local development: Next.js may run on localhost or 127.0.0.1,
    # and may move to the next port if 3000 is already occupied.
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": [origin.strip() for origin in app.config["ALLOWED_ORIGINS"].split(",")],
            }
        },
    )

    @app.before_request
    def print_cors_request() -> None:
        print(
            f"[CORS REQUEST] {request.method} {request.path} "
            f"Origin={request.headers.get('Origin')}",
            flush=True,
        )

    @app.after_request
    def print_cors_response(response):
        print(
            f"[CORS RESPONSE] {response.status_code} {request.method} {request.path} "
            f"Access-Control-Allow-Origin={response.headers.get('Access-Control-Allow-Origin')}",
            flush=True,
        )
        return response

    app.register_blueprint(api)
    app.teardown_appcontext(close_db)

    @app.get("/")
    def index() -> dict[str, str]:
        return {
            "service": "url-shortener-api",
            "status": "ok",
            "health": "/health",
        }

    @app.get("/health")
    def health() -> dict[str, str]:
        get_db().execute("SELECT 1").fetchone()
        app.extensions["redis"].ping()
        return {"status": "ok"}

    return app
