from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.security.crypto import decrypt_json, encrypt_json


LATEST_SCHEMA_VERSION = 3
PROFILE_AAD = b"lifegraph:v1:profile"
EVENT_AAD_PREFIX = b"lifegraph:v2:event:"
MEMORY_AAD_PREFIX = b"lifegraph:v2:memory:"
PLAN_AAD_PREFIX = b"lifegraph:v2:plan:"

_CONTENT_TABLES = {
    "event": ("events", "event_date", EVENT_AAD_PREFIX),
    "memory": ("memories", "memory_date", MEMORY_AAD_PREFIX),
    "plan": ("plans", "plan_date", PLAN_AAD_PREFIX),
}


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
        return {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}

    def _ensure_period_columns(
        self,
        connection: sqlite3.Connection,
        table: str,
        date_column: str,
    ) -> None:
        columns = self._columns(connection, table)
        if "time_scope" not in columns:
            connection.execute(
                f"ALTER TABLE {table} ADD COLUMN time_scope TEXT NOT NULL DEFAULT 'day'"
            )
        if "period_key" not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN period_key TEXT")
        connection.execute(
            f"UPDATE {table} SET time_scope='day' WHERE time_scope IS NULL OR time_scope=''"
        )
        connection.execute(
            f"UPDATE {table} SET period_key={date_column} WHERE period_key IS NULL OR period_key=''"
        )
        connection.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{table}_profile_period
            ON {table}(profile_id, time_scope, period_key)
            WHERE deleted_at IS NULL
            """
        )

    def initialize_schema(self) -> None:
        """Create or migrate the encrypted repository to the latest additive schema."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY,
                    nonce BLOB NOT NULL,
                    ciphertext BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    event_date TEXT NOT NULL,
                    time_scope TEXT NOT NULL DEFAULT 'day',
                    period_key TEXT,
                    nonce BLOB NOT NULL,
                    ciphertext BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    deleted_at TEXT,
                    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    memory_date TEXT NOT NULL,
                    time_scope TEXT NOT NULL DEFAULT 'day',
                    period_key TEXT,
                    nonce BLOB NOT NULL,
                    ciphertext BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    deleted_at TEXT,
                    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    plan_date TEXT NOT NULL,
                    time_scope TEXT NOT NULL DEFAULT 'day',
                    period_key TEXT,
                    nonce BLOB NOT NULL,
                    ciphertext BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    deleted_at TEXT,
                    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                );
                """
            )
            for table, date_column, _ in _CONTENT_TABLES.values():
                connection.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_{table}_profile_date
                    ON {table}(profile_id, {date_column})
                    WHERE deleted_at IS NULL
                    """
                )
                self._ensure_period_columns(connection, table, date_column)

            connection.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', ?)",
                (str(LATEST_SCHEMA_VERSION),),
            )

    def schema_version(self) -> int:
        if not self.path.exists():
            return 0
        with self.connect() as connection:
            row = connection.execute(
                "SELECT value FROM schema_meta WHERE key='schema_version'"
            ).fetchone()
        return int(row["value"]) if row else 0

    def save_profile(
        self,
        master_key: bytes,
        profile_id: str,
        payload: dict[str, Any],
        timestamp: str,
    ) -> None:
        nonce, ciphertext = encrypt_json(master_key, payload, aad=PROFILE_AAD)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO profiles(id, nonce, ciphertext, created_at, updated_at, revision)
                VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(id) DO UPDATE SET
                    nonce=excluded.nonce,
                    ciphertext=excluded.ciphertext,
                    updated_at=excluded.updated_at,
                    revision=profiles.revision + 1
                """,
                (profile_id, nonce, ciphertext, timestamp, timestamp),
            )

    def load_profile(self, master_key: bytes) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id, nonce, ciphertext, created_at, updated_at, revision FROM profiles LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        payload = decrypt_json(master_key, row["nonce"], row["ciphertext"], aad=PROFILE_AAD)
        payload.update(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "revision": row["revision"],
            }
        )
        return payload

    @staticmethod
    def _aad(prefix: bytes, content_id: str) -> bytes:
        return prefix + content_id.encode("utf-8")

    def _create_content(
        self,
        master_key: bytes,
        *,
        kind: str,
        content_id: str,
        profile_id: str,
        anchor_date: str,
        time_scope: str,
        period_key: str,
        payload: dict[str, Any],
        timestamp: str,
    ) -> dict[str, Any]:
        table, date_column, aad_prefix = _CONTENT_TABLES[kind]
        nonce, ciphertext = encrypt_json(
            master_key,
            payload,
            aad=self._aad(aad_prefix, content_id),
        )
        with self.connect() as connection:
            connection.execute(
                f"""
                INSERT INTO {table}(
                    id, profile_id, {date_column}, time_scope, period_key,
                    nonce, ciphertext, created_at, updated_at, revision, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, NULL)
                """,
                (
                    content_id,
                    profile_id,
                    anchor_date,
                    time_scope,
                    period_key,
                    nonce,
                    ciphertext,
                    timestamp,
                    timestamp,
                ),
            )
        return {
            "id": content_id,
            "profile_id": profile_id,
            date_column: anchor_date,
            "time_scope": time_scope,
            "period_key": period_key,
            **payload,
            "created_at": timestamp,
            "updated_at": timestamp,
            "revision": 1,
        }

    def _list_content_for_period(
        self,
        master_key: bytes,
        *,
        kind: str,
        profile_id: str,
        time_scope: str,
        period_key: str,
    ) -> list[dict[str, Any]]:
        table, date_column, aad_prefix = _CONTENT_TABLES[kind]
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT id, profile_id, {date_column}, time_scope, period_key,
                       nonce, ciphertext, created_at, updated_at, revision
                FROM {table}
                WHERE profile_id=? AND time_scope=? AND period_key=?
                  AND deleted_at IS NULL
                ORDER BY created_at DESC, id DESC
                """,
                (profile_id, time_scope, period_key),
            ).fetchall()

        values: list[dict[str, Any]] = []
        for row in rows:
            payload = decrypt_json(
                master_key,
                row["nonce"],
                row["ciphertext"],
                aad=self._aad(aad_prefix, row["id"]),
            )
            values.append(
                {
                    "id": row["id"],
                    "profile_id": row["profile_id"],
                    date_column: row[date_column],
                    "time_scope": row["time_scope"],
                    "period_key": row["period_key"],
                    **payload,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "revision": row["revision"],
                }
            )
        return values

    def create_event(
        self,
        master_key: bytes,
        *,
        event_id: str,
        profile_id: str,
        event_date: str,
        time_scope: str = "day",
        period_key: str | None = None,
        payload: dict[str, Any],
        timestamp: str,
    ) -> dict[str, Any]:
        return self._create_content(
            master_key,
            kind="event",
            content_id=event_id,
            profile_id=profile_id,
            anchor_date=event_date,
            time_scope=time_scope,
            period_key=period_key or event_date,
            payload=payload,
            timestamp=timestamp,
        )

    def list_events_for_period(
        self, master_key: bytes, *, profile_id: str, time_scope: str, period_key: str
    ) -> list[dict[str, Any]]:
        return self._list_content_for_period(
            master_key,
            kind="event",
            profile_id=profile_id,
            time_scope=time_scope,
            period_key=period_key,
        )

    def list_events_for_date(
        self, master_key: bytes, *, profile_id: str, event_date: str
    ) -> list[dict[str, Any]]:
        return self.list_events_for_period(
            master_key, profile_id=profile_id, time_scope="day", period_key=event_date
        )

    def create_memory(
        self,
        master_key: bytes,
        *,
        memory_id: str,
        profile_id: str,
        memory_date: str,
        time_scope: str = "day",
        period_key: str | None = None,
        payload: dict[str, Any],
        timestamp: str,
    ) -> dict[str, Any]:
        return self._create_content(
            master_key,
            kind="memory",
            content_id=memory_id,
            profile_id=profile_id,
            anchor_date=memory_date,
            time_scope=time_scope,
            period_key=period_key or memory_date,
            payload=payload,
            timestamp=timestamp,
        )

    def list_memories_for_period(
        self, master_key: bytes, *, profile_id: str, time_scope: str, period_key: str
    ) -> list[dict[str, Any]]:
        return self._list_content_for_period(
            master_key,
            kind="memory",
            profile_id=profile_id,
            time_scope=time_scope,
            period_key=period_key,
        )

    def list_memories_for_date(
        self, master_key: bytes, *, profile_id: str, memory_date: str
    ) -> list[dict[str, Any]]:
        return self.list_memories_for_period(
            master_key, profile_id=profile_id, time_scope="day", period_key=memory_date
        )

    def create_plan(
        self,
        master_key: bytes,
        *,
        plan_id: str,
        profile_id: str,
        plan_date: str,
        time_scope: str = "day",
        period_key: str | None = None,
        payload: dict[str, Any],
        timestamp: str,
    ) -> dict[str, Any]:
        return self._create_content(
            master_key,
            kind="plan",
            content_id=plan_id,
            profile_id=profile_id,
            anchor_date=plan_date,
            time_scope=time_scope,
            period_key=period_key or plan_date,
            payload=payload,
            timestamp=timestamp,
        )

    def list_plans_for_period(
        self, master_key: bytes, *, profile_id: str, time_scope: str, period_key: str
    ) -> list[dict[str, Any]]:
        return self._list_content_for_period(
            master_key,
            kind="plan",
            profile_id=profile_id,
            time_scope=time_scope,
            period_key=period_key,
        )

    def list_plans_for_date(
        self, master_key: bytes, *, profile_id: str, plan_date: str
    ) -> list[dict[str, Any]]:
        return self.list_plans_for_period(
            master_key, profile_id=profile_id, time_scope="day", period_key=plan_date
        )

    @staticmethod
    def _empty_state() -> dict[str, bool]:
        return {"has_event": False, "has_memory": False, "has_plan": False}

    def get_content_status(
        self,
        *,
        profile_id: str,
        start_date: str,
        end_date: str,
    ) -> dict[str, dict[str, dict[str, bool]]]:
        result: dict[str, dict[str, dict[str, bool]]] = {
            "dates": {},
            "months": {},
            "years": {},
        }
        kinds = (
            ("event", "has_event"),
            ("memory", "has_memory"),
            ("plan", "has_plan"),
        )
        with self.connect() as connection:
            for kind, flag in kinds:
                table, date_column, _ = _CONTENT_TABLES[kind]
                rows = connection.execute(
                    f"""
                    SELECT {date_column} AS anchor_date, time_scope, period_key
                    FROM {table}
                    WHERE profile_id=?
                      AND {date_column} BETWEEN ? AND ?
                      AND deleted_at IS NULL
                    """,
                    (profile_id, start_date, end_date),
                ).fetchall()
                for row in rows:
                    scope = row["time_scope"] or "day"
                    key = row["period_key"] or row["anchor_date"]
                    target_maps: list[tuple[str, str]] = []
                    if scope == "day":
                        target_maps.extend(
                            [
                                ("dates", key),
                                ("months", key[:7]),
                                ("years", key[:4]),
                            ]
                        )
                    elif scope == "month":
                        target_maps.extend([("months", key), ("years", key[:4])])
                    elif scope == "year":
                        target_maps.append(("years", key))
                    for map_name, map_key in target_maps:
                        state = result[map_name].setdefault(map_key, self._empty_state())
                        state[flag] = True
        return result
