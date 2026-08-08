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



def test_schema_v4_memory_tags_are_migrated_to_unified_content_tags(tmp_path: Path) -> None:
    database_path = tmp_path / "lifegraph.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO schema_meta(key, value) VALUES('schema_version', '4');
            CREATE TABLE profiles (
                id TEXT PRIMARY KEY, nonce BLOB NOT NULL, ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1
            );
            INSERT INTO profiles VALUES('profile-1', X'00', X'01', '2026-08-08', '2026-08-08', 1);
            CREATE TABLE memories (
                id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, memory_date TEXT NOT NULL,
                time_scope TEXT NOT NULL DEFAULT 'day', period_key TEXT,
                nonce BLOB NOT NULL, ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1, deleted_at TEXT
            );
            INSERT INTO memories VALUES(
                'memory-1', 'profile-1', '2026-08-08', 'day', '2026-08-08',
                X'00', X'01', '2026-08-08', '2026-08-08', 1, NULL
            );
            CREATE TABLE tags (
                id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, name TEXT NOT NULL, color TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            INSERT INTO tags VALUES('tag-1', 'profile-1', '旧标签', NULL, '2026-08-08', '2026-08-08');
            CREATE TABLE memory_tags (
                memory_id TEXT NOT NULL, tag_id TEXT NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(memory_id, tag_id)
            );
            INSERT INTO memory_tags VALUES('memory-1', 'tag-1', '2026-08-08');
            """
        )

    database = Database(database_path)
    database.initialize_schema()

    assert database.schema_version() == LATEST_SCHEMA_VERSION
    with database.connect() as connection:
        row = connection.execute(
            "SELECT kind, content_id, tag_id FROM content_tags"
        ).fetchone()
        legacy_count = connection.execute("SELECT COUNT(*) FROM memory_tags").fetchone()[0]
    assert dict(row) == {"kind": "memory", "content_id": "memory-1", "tag_id": "tag-1"}
    assert legacy_count == 0

    # Running migrations again must not recreate a link that was removed in v5.
    with database.connect() as connection:
        connection.execute(
            "DELETE FROM content_tags WHERE kind='memory' AND content_id='memory-1' AND tag_id='tag-1'"
        )
    database.initialize_schema()
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM content_tags").fetchone()[0] == 0
