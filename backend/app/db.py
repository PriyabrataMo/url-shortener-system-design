from __future__ import annotations

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from flask import Flask, current_app, g


def get_db():
    if "db" not in g:
        g.db = current_app.extensions["db_pool"].getconn()
    return g.db


def init_db(app: Flask) -> None:
    pool = ConnectionPool(
        conninfo=app.config["DATABASE_URL"],
        min_size=1,
        max_size=10,
        kwargs={"row_factory": dict_row},
    )
    app.extensions["db_pool"] = pool
    with pool.connection() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS url_mappings (
                code TEXT PRIMARY KEY,
                long_url TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                clicks BIGINT NOT NULL DEFAULT 0
            );
            ALTER TABLE url_mappings
            ALTER COLUMN clicks TYPE BIGINT;
            """
        )


def close_db(_error: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.rollback()
        current_app.extensions["db_pool"].putconn(db)
