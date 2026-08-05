from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.security.crypto import decrypt_json, encrypt_json


LATEST_SCHEMA_VERSION = 2
PROFILE_AAD = b"lifegraph:v1:profile"
EVENT_AAD_PREFIX = b"lifegraph:v2:event:"
MEMORY_AAD_PREFIX = b"lifegraph:v2:memory:"
PLAN_AAD_PREFIX = b"lifegraph:v2:plan:"


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def initialize_schema(self) -> None:
        """Create the latest schema or migrate an existing Stage 0 database.

        Migrations are intentionally additive in v0.0.2: existing encrypted profile
        rows are left untouched while the content tables are added idempotently.
        """
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
                    nonce BLOB NOT NULL,
                    ciphertext BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    deleted_at TEXT,
                    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_events_profile_date
                    ON events(profile_id, event_date)
                    WHERE deleted_at IS NULL;

                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    memory_date TEXT NOT NULL,
                    nonce BLOB NOT NULL,
                    ciphertext BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    deleted_at TEXT,
                    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_memories_profile_date
                    ON memories(profile_id, memory_date)
                    WHERE deleted_at IS NULL;

                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    plan_date TEXT NOT NULL,
                    nonce BLOB NOT NULL,
                    ciphertext BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    deleted_at TEXT,
                    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_plans_profile_date
                    ON plans(profile_id, plan_date)
                    WHERE deleted_at IS NULL;
                """
            )
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
    def _event_aad(event_id: str) -> bytes:
        return EVENT_AAD_PREFIX + event_id.encode("utf-8")

    @staticmethod
    def _memory_aad(memory_id: str) -> bytes:
        return MEMORY_AAD_PREFIX + memory_id.encode("utf-8")

    @staticmethod
    def _plan_aad(plan_id: str) -> bytes:
        return PLAN_AAD_PREFIX + plan_id.encode("utf-8")

    def create_event(
        self,
        master_key: bytes,
        *,
        event_id: str,
        profile_id: str,
        event_date: str,
        payload: dict[str, Any],
        timestamp: str,
    ) -> dict[str, Any]:
        nonce, ciphertext = encrypt_json(
            master_key,
            payload,
            aad=self._event_aad(event_id),
        )
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO events(
                    id, profile_id, event_date, nonce, ciphertext,
                    created_at, updated_at, revision, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, NULL)
                """,
                (
                    event_id,
                    profile_id,
                    event_date,
                    nonce,
                    ciphertext,
                    timestamp,
                    timestamp,
                ),
            )
        return {
            "id": event_id,
            "profile_id": profile_id,
            "event_date": event_date,
            **payload,
            "created_at": timestamp,
            "updated_at": timestamp,
            "revision": 1,
        }

    def list_events_for_date(
        self,
        master_key: bytes,
        *,
        profile_id: str,
        event_date: str,
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, profile_id, event_date, nonce, ciphertext,
                       created_at, updated_at, revision
                FROM events
                WHERE profile_id=? AND event_date=? AND deleted_at IS NULL
                ORDER BY created_at DESC, id DESC
                """,
                (profile_id, event_date),
            ).fetchall()

        events: list[dict[str, Any]] = []
        for row in rows:
            payload = decrypt_json(
                master_key,
                row["nonce"],
                row["ciphertext"],
                aad=self._event_aad(row["id"]),
            )
            events.append(
                {
                    "id": row["id"],
                    "profile_id": row["profile_id"],
                    "event_date": row["event_date"],
                    **payload,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "revision": row["revision"],
                }
            )
        return events

    def create_memory(
        self,
        master_key: bytes,
        *,
        memory_id: str,
        profile_id: str,
        memory_date: str,
        payload: dict[str, Any],
        timestamp: str,
    ) -> dict[str, Any]:
        nonce, ciphertext = encrypt_json(
            master_key,
            payload,
            aad=self._memory_aad(memory_id),
        )
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO memories(
                    id, profile_id, memory_date, nonce, ciphertext,
                    created_at, updated_at, revision, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, NULL)
                """,
                (
                    memory_id,
                    profile_id,
                    memory_date,
                    nonce,
                    ciphertext,
                    timestamp,
                    timestamp,
                ),
            )
        return {
            "id": memory_id,
            "profile_id": profile_id,
            "memory_date": memory_date,
            **payload,
            "created_at": timestamp,
            "updated_at": timestamp,
            "revision": 1,
        }

    def list_memories_for_date(
        self,
        master_key: bytes,
        *,
        profile_id: str,
        memory_date: str,
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, profile_id, memory_date, nonce, ciphertext,
                       created_at, updated_at, revision
                FROM memories
                WHERE profile_id=? AND memory_date=? AND deleted_at IS NULL
                ORDER BY created_at DESC, id DESC
                """,
                (profile_id, memory_date),
            ).fetchall()

        memories: list[dict[str, Any]] = []
        for row in rows:
            payload = decrypt_json(
                master_key,
                row["nonce"],
                row["ciphertext"],
                aad=self._memory_aad(row["id"]),
            )
            memories.append(
                {
                    "id": row["id"],
                    "profile_id": row["profile_id"],
                    "memory_date": row["memory_date"],
                    **payload,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "revision": row["revision"],
                }
            )
        return memories

    def create_plan(
        self,
        master_key: bytes,
        *,
        plan_id: str,
        profile_id: str,
        plan_date: str,
        payload: dict[str, Any],
        timestamp: str,
    ) -> dict[str, Any]:
        nonce, ciphertext = encrypt_json(
            master_key,
            payload,
            aad=self._plan_aad(plan_id),
        )
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO plans(
                    id, profile_id, plan_date, nonce, ciphertext,
                    created_at, updated_at, revision, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, NULL)
                """,
                (
                    plan_id,
                    profile_id,
                    plan_date,
                    nonce,
                    ciphertext,
                    timestamp,
                    timestamp,
                ),
            )
        return {
            "id": plan_id,
            "profile_id": profile_id,
            "plan_date": plan_date,
            **payload,
            "created_at": timestamp,
            "updated_at": timestamp,
            "revision": 1,
        }

    def list_plans_for_date(
        self,
        master_key: bytes,
        *,
        profile_id: str,
        plan_date: str,
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, profile_id, plan_date, nonce, ciphertext,
                       created_at, updated_at, revision
                FROM plans
                WHERE profile_id=? AND plan_date=? AND deleted_at IS NULL
                ORDER BY created_at DESC, id DESC
                """,
                (profile_id, plan_date),
            ).fetchall()

        plans: list[dict[str, Any]] = []
        for row in rows:
            payload = decrypt_json(
                master_key,
                row["nonce"],
                row["ciphertext"],
                aad=self._plan_aad(row["id"]),
            )
            plans.append(
                {
                    "id": row["id"],
                    "profile_id": row["profile_id"],
                    "plan_date": row["plan_date"],
                    **payload,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "revision": row["revision"],
                }
            )
        return plans

    def get_content_status(
        self,
        *,
        profile_id: str,
        start_date: str,
        end_date: str,
    ) -> dict[str, dict[str, bool]]:
        result: dict[str, dict[str, bool]] = {}
        queries = (
            ("events", "event_date", "has_event"),
            ("memories", "memory_date", "has_memory"),
            ("plans", "plan_date", "has_plan"),
        )
        with self.connect() as connection:
            for table, date_column, flag in queries:
                rows = connection.execute(
                    f"""
                    SELECT DISTINCT {date_column} AS content_date
                    FROM {table}
                    WHERE profile_id=?
                      AND {date_column} BETWEEN ? AND ?
                      AND deleted_at IS NULL
                    """,
                    (profile_id, start_date, end_date),
                ).fetchall()
                for row in rows:
                    state = result.setdefault(
                        row["content_date"],
                        {
                            "has_event": False,
                            "has_memory": False,
                            "has_plan": False,
                        },
                    )
                    state[flag] = True
        return result
