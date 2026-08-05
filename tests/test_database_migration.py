import sqlite3
from pathlib import Path

from app.storage.database import Database, LATEST_SCHEMA_VERSION


def test_stage0_database_migrates_to_schema_v2(tmp_path: Path) -> None:
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
    database.initialize_schema()  # migration must be safe to repeat

    assert database.schema_version() == LATEST_SCHEMA_VERSION
    with database.connect() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {"schema_meta", "profiles", "events", "memories", "plans"}.issubset(tables)
