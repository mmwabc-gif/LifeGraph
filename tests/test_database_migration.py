import sqlite3
from pathlib import Path

from app.storage.database import Database, LATEST_SCHEMA_VERSION


def test_stage0_database_migrates_to_latest_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "lifegraph.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            INSERT INTO schema_meta(key, value) VALUES('schema_version', '1');

            CREATE TABLE profiles (
                id TEXT PRIMARY KEY,
                nonce BLOB NOT NULL,
                ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1
            );
            """
        )

    database = Database(database_path)
    database.initialize_schema()
    database.initialize_schema()

    assert database.schema_version() == LATEST_SCHEMA_VERSION
    with database.connect() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert {"schema_meta", "profiles", "events", "memories", "plans"}.issubset(tables)
        for table in ("events", "memories", "plans"):
            columns = {
                row["name"] for row in connection.execute(f"PRAGMA table_info({table})")
            }
            assert {"time_scope", "period_key"}.issubset(columns)


def test_schema_v2_day_content_is_backfilled_as_day_scope(tmp_path: Path) -> None:
    database_path = tmp_path / "lifegraph.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO schema_meta(key, value) VALUES('schema_version', '2');
            CREATE TABLE profiles (
                id TEXT PRIMARY KEY, nonce BLOB NOT NULL, ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE events (
                id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, event_date TEXT NOT NULL,
                nonce BLOB NOT NULL, ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1, deleted_at TEXT
            );
            INSERT INTO events VALUES(
                'event-1', 'profile-1', '2026-08-05', X'00', X'01',
                '2026-08-05T00:00:00Z', '2026-08-05T00:00:00Z', 1, NULL
            );
            CREATE TABLE memories (
                id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, memory_date TEXT NOT NULL,
                nonce BLOB NOT NULL, ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1, deleted_at TEXT
            );
            CREATE TABLE plans (
                id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, plan_date TEXT NOT NULL,
                nonce BLOB NOT NULL, ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1, deleted_at TEXT
            );
            """
        )

    database = Database(database_path)
    database.initialize_schema()

    with database.connect() as connection:
        row = connection.execute(
            "SELECT time_scope, period_key FROM events WHERE id='event-1'"
        ).fetchone()
    assert row["time_scope"] == "day"
    assert row["period_key"] == "2026-08-05"
