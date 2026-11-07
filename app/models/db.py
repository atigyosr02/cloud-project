from contextlib import contextmanager
from typing import Any, Iterator

import psycopg2
from flask import current_app
from psycopg2.extras import RealDictCursor


def connect():
    return psycopg2.connect(
        host=current_app.config["DB_HOST"],
        port=current_app.config["DB_PORT"],
        dbname=current_app.config["DB_NAME"],
        user=current_app.config["DB_USER"],
        password=current_app.config["DB_PASSWORD"],
        connect_timeout=4,
        sslmode=current_app.config.get("DB_SSLMODE", "prefer"),
        sslrootcert=current_app.config.get("DB_SSLROOTCERT"),
    )


@contextmanager
def get_db() -> Iterator[Any]:
    connection = connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def fetch_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with get_db() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None


def fetch_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with get_db() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def execute(sql: str, params: tuple[Any, ...] = ()) -> int:
    with get_db() as connection, connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.rowcount


def database_health() -> bool:
    try:
        with get_db() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone()[0] == 1
    except Exception:
        return False