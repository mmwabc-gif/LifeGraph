from __future__ import annotations

import html
import re
import sqlite3
from pathlib import Path
from typing import Any

from app.security.crypto import decrypt_json, encrypt_json


LATEST_SCHEMA_VERSION = 4
PROFILE_AAD = b"lifegraph:v1:profile"
EVENT_AAD_PREFIX = b"lifegraph:v2:event:"
MEMORY_AAD_PREFIX = b"lifegraph:v2:memory:"
PLAN_AAD_PREFIX = b"lifegraph:v2:plan:"

_CONTENT_TABLES = {
    "event": ("events", "event_date", EVENT_AAD_PREFIX),
    "memory": ("memories", "memory_date", MEMORY_AAD_PREFIX),
    "plan": ("plans", "plan_date", PLAN_AAD_PREFIX),
}


class DatabaseContentNotFound(LookupError):
    pass


class DatabaseRevisionConflict(RuntimeError):
    pass


class DatabaseIntegrityError(RuntimeError):
    pass


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
                CREATE TABLE IF NOT EXISTS tags (
                    id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    color TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS memory_tags (
                    memory_id TEXT NOT NULL,
                    tag_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(memory_id, tag_id),
                    FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE,
                    FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_tags_profile
                ON tags(profile_id, name);

                CREATE INDEX IF NOT EXISTS idx_memory_tags_memory
                ON memory_tags(memory_id);


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

    def create_consistent_snapshot(self, destination: Path) -> None:
        """Copy one committed SQLite state to a standalone database file."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.unlink(missing_ok=True)
        with self.connect() as source, sqlite3.connect(destination) as target:
            # PASSIVE checkpoint reduces stale WAL pages without blocking writers.
            source.execute("PRAGMA wal_checkpoint(PASSIVE)")
            source.backup(target)
            target.commit()

    @staticmethod
    def _readonly_connection(path: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def verify_encrypted_snapshot(
        self, snapshot_path: Path, master_key: bytes
    ) -> dict[str, Any]:
        """Verify SQLite structure and decrypt every encrypted repository row."""
        if not snapshot_path.exists():
            raise DatabaseIntegrityError("数据库快照不存在")
        with self._readonly_connection(snapshot_path) as connection:
            quick_rows = [row[0] for row in connection.execute("PRAGMA quick_check")]
            if quick_rows != ["ok"]:
                raise DatabaseIntegrityError(
                    "SQLite 完整性检查失败：" + "；".join(map(str, quick_rows))
                )
            foreign_key_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
            if foreign_key_rows:
                raise DatabaseIntegrityError(
                    f"SQLite 外键检查发现 {len(foreign_key_rows)} 个问题"
                )

            schema_row = connection.execute(
                "SELECT value FROM schema_meta WHERE key='schema_version'"
            ).fetchone()
            if schema_row is None:
                raise DatabaseIntegrityError("数据库缺少 schema_version")
            schema_version = int(schema_row["value"])

            profile_rows = connection.execute(
                "SELECT id, nonce, ciphertext FROM profiles"
            ).fetchall()
            if len(profile_rows) != 1:
                raise DatabaseIntegrityError(
                    f"个人档案数量异常：应为 1，实际为 {len(profile_rows)}"
                )
            for row in profile_rows:
                decrypt_json(
                    master_key, row["nonce"], row["ciphertext"], aad=PROFILE_AAD
                )

            verified_records = len(profile_rows)
            counts: dict[str, int] = {"profile": len(profile_rows)}
            for kind, (table, _date_column, aad_prefix) in _CONTENT_TABLES.items():
                rows = connection.execute(
                    f"SELECT id, nonce, ciphertext FROM {table}"
                ).fetchall()
                for row in rows:
                    decrypt_json(
                        master_key,
                        row["nonce"],
                        row["ciphertext"],
                        aad=self._aad(aad_prefix, row["id"]),
                    )
                counts[kind] = len(rows)
                verified_records += len(rows)

        return {
            "sqlite_quick_check": "ok",
            "foreign_key_errors": 0,
            "schema_version": schema_version,
            "encrypted_records_verified": verified_records,
            "record_counts": counts,
        }

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


    def update_profile(
        self,
        master_key: bytes,
        *,
        profile_id: str,
        payload: dict[str, Any],
        expected_revision: int,
        timestamp: str,
    ) -> dict[str, Any]:
        nonce, ciphertext = encrypt_json(master_key, payload, aad=PROFILE_AAD)
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE profiles
                SET nonce=?, ciphertext=?, updated_at=?, revision=revision + 1
                WHERE id=? AND revision=?
                """,
                (nonce, ciphertext, timestamp, profile_id, expected_revision),
            )
            if cursor.rowcount != 1:
                row = connection.execute(
                    "SELECT revision FROM profiles WHERE id=?", (profile_id,)
                ).fetchone()
                if row is None:
                    raise DatabaseContentNotFound("个人档案不存在")
                raise DatabaseRevisionConflict("个人档案已被更新，请刷新后重试")
        profile = self.load_profile(master_key)
        if profile is None:  # pragma: no cover - defensive
            raise DatabaseContentNotFound("个人档案不存在")
        return profile

    def list_active_period_references(self, *, profile_id: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        with self.connect() as connection:
            for kind, (table, _date_column, _aad_prefix) in _CONTENT_TABLES.items():
                for row in connection.execute(
                    f"""
                    SELECT time_scope, period_key
                    FROM {table}
                    WHERE profile_id=? AND deleted_at IS NULL
                    """,
                    (profile_id,),
                ):
                    rows.append(
                        {
                            "kind": kind,
                            "time_scope": row["time_scope"],
                            "period_key": row["period_key"],
                        }
                    )
        return rows

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

    def _update_content(
        self,
        master_key: bytes,
        *,
        kind: str,
        content_id: str,
        profile_id: str,
        payload: dict[str, Any],
        expected_revision: int,
        timestamp: str,
    ) -> dict[str, Any]:
        table, date_column, aad_prefix = _CONTENT_TABLES[kind]
        nonce, ciphertext = encrypt_json(
            master_key,
            payload,
            aad=self._aad(aad_prefix, content_id),
        )
        with self.connect() as connection:
            cursor = connection.execute(
                f"""
                UPDATE {table}
                SET nonce=?, ciphertext=?, updated_at=?, revision=revision + 1
                WHERE id=? AND profile_id=? AND deleted_at IS NULL AND revision=?
                """,
                (
                    nonce,
                    ciphertext,
                    timestamp,
                    content_id,
                    profile_id,
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                row = connection.execute(
                    f"""
                    SELECT revision
                    FROM {table}
                    WHERE id=? AND profile_id=? AND deleted_at IS NULL
                    """,
                    (content_id, profile_id),
                ).fetchone()
                if row is None:
                    raise DatabaseContentNotFound("内容不存在或已经被删除")
                raise DatabaseRevisionConflict(
                    f"内容已被其他操作更新，当前版本为 {row['revision']}"
                )

            row = connection.execute(
                f"""
                SELECT id, profile_id, {date_column}, time_scope, period_key,
                       created_at, updated_at, revision
                FROM {table}
                WHERE id=? AND profile_id=?
                """,
                (content_id, profile_id),
            ).fetchone()

        if row is None:
            raise DatabaseContentNotFound("内容不存在或已经被删除")
        return {
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

    def _soft_delete_content(
        self,
        *,
        kind: str,
        content_id: str,
        profile_id: str,
        expected_revision: int,
        timestamp: str,
    ) -> dict[str, Any]:
        table, _, _ = _CONTENT_TABLES[kind]
        with self.connect() as connection:
            cursor = connection.execute(
                f"""
                UPDATE {table}
                SET deleted_at=?, updated_at=?, revision=revision + 1
                WHERE id=? AND profile_id=? AND deleted_at IS NULL AND revision=?
                """,
                (timestamp, timestamp, content_id, profile_id, expected_revision),
            )
            if cursor.rowcount != 1:
                row = connection.execute(
                    f"""
                    SELECT revision, deleted_at
                    FROM {table}
                    WHERE id=? AND profile_id=?
                    """,
                    (content_id, profile_id),
                ).fetchone()
                if row is None or row["deleted_at"] is not None:
                    raise DatabaseContentNotFound("内容不存在或已经被删除")
                raise DatabaseRevisionConflict(
                    f"内容已被其他操作更新，当前版本为 {row['revision']}"
                )

            row = connection.execute(
                f"""
                SELECT id, updated_at, revision, deleted_at
                FROM {table}
                WHERE id=? AND profile_id=?
                """,
                (content_id, profile_id),
            ).fetchone()

        if row is None:
            raise DatabaseContentNotFound("内容不存在或已经被删除")
        return {
            "id": row["id"],
            "updated_at": row["updated_at"],
            "revision": row["revision"],
            "deleted_at": row["deleted_at"],
        }

    def list_deleted_content(
        self,
        master_key: bytes,
        *,
        profile_id: str,
    ) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        with self.connect() as connection:
            for kind, (table, date_column, aad_prefix) in _CONTENT_TABLES.items():
                rows = connection.execute(
                    f"""
                    SELECT id, profile_id, {date_column}, time_scope, period_key,
                           nonce, ciphertext, created_at, updated_at, revision, deleted_at
                    FROM {table}
                    WHERE profile_id=? AND deleted_at IS NOT NULL
                    ORDER BY deleted_at DESC, id DESC
                    """,
                    (profile_id,),
                ).fetchall()
                for row in rows:
                    payload = decrypt_json(
                        master_key,
                        row["nonce"],
                        row["ciphertext"],
                        aad=self._aad(aad_prefix, row["id"]),
                    )
                    values.append(
                        {
                            "kind": kind,
                            "id": row["id"],
                            "profile_id": row["profile_id"],
                            "anchor_date": row[date_column],
                            date_column: row[date_column],
                            "time_scope": row["time_scope"],
                            "period_key": row["period_key"],
                            **payload,
                            "created_at": row["created_at"],
                            "updated_at": row["updated_at"],
                            "revision": row["revision"],
                            "deleted_at": row["deleted_at"],
                        }
                    )
        values.sort(key=lambda value: (value["deleted_at"], value["id"]), reverse=True)
        return values

    def restore_deleted_content(
        self,
        *,
        kind: str,
        content_id: str,
        profile_id: str,
        expected_revision: int,
        timestamp: str,
    ) -> dict[str, Any]:
        table, _, _ = _CONTENT_TABLES[kind]
        with self.connect() as connection:
            cursor = connection.execute(
                f"""
                UPDATE {table}
                SET deleted_at=NULL, updated_at=?, revision=revision + 1
                WHERE id=? AND profile_id=? AND deleted_at IS NOT NULL AND revision=?
                """,
                (timestamp, content_id, profile_id, expected_revision),
            )
            if cursor.rowcount != 1:
                row = connection.execute(
                    f"SELECT revision, deleted_at FROM {table} WHERE id=? AND profile_id=?",
                    (content_id, profile_id),
                ).fetchone()
                if row is None or row["deleted_at"] is None:
                    raise DatabaseContentNotFound("回收站内容不存在或已经恢复")
                raise DatabaseRevisionConflict(
                    f"内容已被其他操作更新，当前版本为 {row['revision']}"
                )
            row = connection.execute(
                f"SELECT id, updated_at, revision FROM {table} WHERE id=? AND profile_id=?",
                (content_id, profile_id),
            ).fetchone()
        if row is None:
            raise DatabaseContentNotFound("回收站内容不存在或已经恢复")
        return {
            "kind": kind,
            "id": row["id"],
            "updated_at": row["updated_at"],
            "revision": row["revision"],
            "restored": True,
        }

    def permanently_delete_content(
        self,
        *,
        kind: str,
        content_id: str,
        profile_id: str,
        expected_revision: int,
    ) -> dict[str, Any]:
        table, _, _ = _CONTENT_TABLES[kind]
        with self.connect() as connection:
            row = connection.execute(
                f"SELECT revision, deleted_at FROM {table} WHERE id=? AND profile_id=?",
                (content_id, profile_id),
            ).fetchone()
            if row is None or row["deleted_at"] is None:
                raise DatabaseContentNotFound("回收站内容不存在或已经恢复")
            if row["revision"] != expected_revision:
                raise DatabaseRevisionConflict(
                    f"内容已被其他操作更新，当前版本为 {row['revision']}"
                )
            connection.execute(
                f"DELETE FROM {table} WHERE id=? AND profile_id=? AND deleted_at IS NOT NULL",
                (content_id, profile_id),
            )
        return {
            "kind": kind,
            "id": content_id,
            "permanently_deleted": True,
        }

    def empty_trash(self, *, profile_id: str) -> dict[str, Any]:
        counts: dict[str, int] = {}
        with self.connect() as connection:
            for kind, (table, _, _) in _CONTENT_TABLES.items():
                cursor = connection.execute(
                    f"DELETE FROM {table} WHERE profile_id=? AND deleted_at IS NOT NULL",
                    (profile_id,),
                )
                counts[kind] = cursor.rowcount
        return {
            "counts": counts,
            "total": sum(counts.values()),
            "emptied": True,
        }

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

    def update_event(
        self,
        master_key: bytes,
        *,
        event_id: str,
        profile_id: str,
        payload: dict[str, Any],
        expected_revision: int,
        timestamp: str,
    ) -> dict[str, Any]:
        return self._update_content(
            master_key,
            kind="event",
            content_id=event_id,
            profile_id=profile_id,
            payload=payload,
            expected_revision=expected_revision,
            timestamp=timestamp,
        )

    def delete_event(
        self,
        *,
        event_id: str,
        profile_id: str,
        expected_revision: int,
        timestamp: str,
    ) -> dict[str, Any]:
        return self._soft_delete_content(
            kind="event",
            content_id=event_id,
            profile_id=profile_id,
            expected_revision=expected_revision,
            timestamp=timestamp,
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

    def search_memories(
        self,
        master_key: bytes,
        *,
        profile_id: str,
        query: str = "",
        tag_ids: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        tag_ids = list(dict.fromkeys(tag_ids or []))
        where = ["m.profile_id=?", "m.deleted_at IS NULL"]
        params: list[Any] = [profile_id]

        if date_from:
            where.append("m.memory_date>=?")
            params.append(date_from)
        if date_to:
            where.append("m.memory_date<=?")
            params.append(date_to)
        if tag_ids:
            placeholders = ",".join("?" for _ in tag_ids)
            where.append(
                f"""
                m.id IN (
                    SELECT mt.memory_id
                    FROM memory_tags mt
                    JOIN tags t ON t.id=mt.tag_id
                    WHERE t.profile_id=? AND mt.tag_id IN ({placeholders})
                    GROUP BY mt.memory_id
                    HAVING COUNT(DISTINCT mt.tag_id)=?
                )
                """
            )
            params.extend([profile_id, *tag_ids, len(tag_ids)])

        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT m.id, m.profile_id, m.memory_date, m.time_scope, m.period_key,
                       m.nonce, m.ciphertext, m.created_at, m.updated_at, m.revision
                FROM memories m
                WHERE {' AND '.join(where)}
                ORDER BY m.memory_date DESC, m.created_at DESC, m.id DESC
                """,
                params,
            ).fetchall()

        normalized_query = query.strip().casefold()
        values: list[dict[str, Any]] = []
        has_more = False
        for row in rows:
            payload = decrypt_json(
                master_key,
                row["nonce"],
                row["ciphertext"],
                aad=self._aad(MEMORY_AAD_PREFIX, row["id"]),
            )
            if normalized_query:
                content = str(payload.get("content", ""))
                if payload.get("content_format") == "html":
                    content = html.unescape(re.sub(r"<[^>]+>", " ", content))
                content = re.sub(r"\s+", " ", content).strip()
                haystack = f"{payload.get('title', '')}\n{content}".casefold()
                if normalized_query not in haystack:
                    continue
            values.append(
                {
                    "id": row["id"],
                    "profile_id": row["profile_id"],
                    "memory_date": row["memory_date"],
                    "time_scope": row["time_scope"],
                    "period_key": row["period_key"],
                    **payload,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "revision": row["revision"],
                }
            )
            if len(values) > limit:
                has_more = True
                values = values[:limit]
                break

        tags_by_memory = self.list_memory_tags_for_memories(
            profile_id=profile_id, memory_ids=[item["id"] for item in values]
        )
        for item in values:
            item["tags"] = tags_by_memory.get(item["id"], [])
        return {"items": values, "count": len(values), "has_more": has_more}

    def get_memory_tag_map(
        self,
        *,
        profile_id: str,
        tag_ids: list[str],
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        tag_ids = list(dict.fromkeys(tag_ids))
        result: dict[str, Any] = {
            "dates": [],
            "months": [],
            "years": [],
            "memory_count": 0,
        }
        if not tag_ids:
            return result

        placeholders = ",".join("?" for _ in tag_ids)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT m.id, m.memory_date, m.time_scope, m.period_key
                FROM memories m
                JOIN memory_tags mt ON mt.memory_id=m.id
                JOIN tags t ON t.id=mt.tag_id
                WHERE m.profile_id=? AND t.profile_id=?
                  AND m.deleted_at IS NULL
                  AND mt.tag_id IN ({placeholders})
                GROUP BY m.id, m.memory_date, m.time_scope, m.period_key
                HAVING COUNT(DISTINCT mt.tag_id)=?
                ORDER BY m.memory_date, m.created_at, m.id
                """,
                (profile_id, profile_id, *tag_ids, len(tag_ids)),
            ).fetchall()

        dates: set[str] = set()
        months: set[str] = set()
        years: set[str] = set()
        visible_memory_ids: set[str] = set()
        for row in rows:
            scope = row["time_scope"] or "day"
            key = row["period_key"] or row["memory_date"]
            if scope == "day":
                visible = start_date <= key <= end_date
            elif scope == "month":
                visible = start_date[:7] <= key[:7] <= end_date[:7]
            elif scope == "year":
                visible = start_date[:4] <= key[:4] <= end_date[:4]
            else:
                visible = False
            if not visible:
                continue

            visible_memory_ids.add(row["id"])
            if scope == "day":
                dates.add(key)
                months.add(key[:7])
                years.add(key[:4])
            elif scope == "month":
                months.add(key[:7])
                years.add(key[:4])
            elif scope == "year":
                years.add(key[:4])

        result["dates"] = sorted(dates)
        result["months"] = sorted(months)
        result["years"] = sorted(years)
        result["memory_count"] = len(visible_memory_ids)
        return result

    def update_memory(
        self,
        master_key: bytes,
        *,
        memory_id: str,
        profile_id: str,
        payload: dict[str, Any],
        expected_revision: int,
        timestamp: str,
    ) -> dict[str, Any]:
        return self._update_content(
            master_key,
            kind="memory",
            content_id=memory_id,
            profile_id=profile_id,
            payload=payload,
            expected_revision=expected_revision,
            timestamp=timestamp,
        )

    def delete_memory(
        self,
        *,
        memory_id: str,
        profile_id: str,
        expected_revision: int,
        timestamp: str,
    ) -> dict[str, Any]:
        return self._soft_delete_content(
            kind="memory",
            content_id=memory_id,
            profile_id=profile_id,
            expected_revision=expected_revision,
            timestamp=timestamp,
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

    def update_plan(
        self,
        master_key: bytes,
        *,
        plan_id: str,
        profile_id: str,
        payload: dict[str, Any],
        expected_revision: int,
        timestamp: str,
    ) -> dict[str, Any]:
        return self._update_content(
            master_key,
            kind="plan",
            content_id=plan_id,
            profile_id=profile_id,
            payload=payload,
            expected_revision=expected_revision,
            timestamp=timestamp,
        )

    def delete_plan(
        self,
        *,
        plan_id: str,
        profile_id: str,
        expected_revision: int,
        timestamp: str,
    ) -> dict[str, Any]:
        return self._soft_delete_content(
            kind="plan",
            content_id=plan_id,
            profile_id=profile_id,
            expected_revision=expected_revision,
            timestamp=timestamp,
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
                    WHERE profile_id=? AND deleted_at IS NULL
                    """,
                    (profile_id,),
                ).fetchall()
                for row in rows:
                    scope = row["time_scope"] or "day"
                    key = row["period_key"] or row["anchor_date"]
                    if scope == "day":
                        visible = start_date <= key <= end_date
                    elif scope == "month":
                        visible = key[:7] <= end_date[:7] and key[:7] >= start_date[:7]
                    elif scope == "year":
                        visible = key[:4] <= end_date[:4] and key[:4] >= start_date[:4]
                    else:
                        visible = False
                    if not visible:
                        continue
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


    def create_tag(self, *, profile_id: str, tag_id: str, name: str, color: str | None, timestamp: str) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO tags(id, profile_id, name, color, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (tag_id, profile_id, name, color, timestamp, timestamp),
            )
            return {
                "id": tag_id,
                "name": name,
                "color": color,
                "created_at": timestamp,
                "updated_at": timestamp,
                "memory_count": 0,
            }

    def list_tags(self, *, profile_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT t.id, t.name, t.color, t.created_at, t.updated_at,
                       COUNT(DISTINCT CASE WHEN m.deleted_at IS NULL THEN mt.memory_id END) AS memory_count
                FROM tags t
                LEFT JOIN memory_tags mt ON mt.tag_id=t.id
                LEFT JOIN memories m ON m.id=mt.memory_id AND m.profile_id=t.profile_id
                WHERE t.profile_id=?
                GROUP BY t.id, t.name, t.color, t.created_at, t.updated_at
                ORDER BY t.name COLLATE NOCASE, t.created_at, t.id
                """,
                (profile_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def update_tag(
        self,
        *,
        profile_id: str,
        tag_id: str,
        name: str,
        color: str | None,
        timestamp: str,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE tags
                SET name=?, color=?, updated_at=?
                WHERE id=? AND profile_id=?
                """,
                (name, color, timestamp, tag_id, profile_id),
            )
            if cursor.rowcount != 1:
                raise DatabaseContentNotFound("标签不存在")
            row = connection.execute(
                """
                SELECT t.id, t.name, t.color, t.created_at, t.updated_at,
                       COUNT(DISTINCT CASE WHEN m.deleted_at IS NULL THEN mt.memory_id END) AS memory_count
                FROM tags t
                LEFT JOIN memory_tags mt ON mt.tag_id=t.id
                LEFT JOIN memories m ON m.id=mt.memory_id AND m.profile_id=t.profile_id
                WHERE t.id=? AND t.profile_id=?
                GROUP BY t.id, t.name, t.color, t.created_at, t.updated_at
                """,
                (tag_id, profile_id),
            ).fetchone()
            if row is None:  # pragma: no cover - defensive
                raise DatabaseContentNotFound("标签不存在")
            return dict(row)

    def delete_tag(self, *, profile_id: str, tag_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT t.id, t.name,
                       COUNT(DISTINCT CASE WHEN m.deleted_at IS NULL THEN mt.memory_id END) AS memory_count
                FROM tags t
                LEFT JOIN memory_tags mt ON mt.tag_id=t.id
                LEFT JOIN memories m ON m.id=mt.memory_id AND m.profile_id=t.profile_id
                WHERE t.id=? AND t.profile_id=?
                GROUP BY t.id, t.name
                """,
                (tag_id, profile_id),
            ).fetchone()
            if row is None:
                raise DatabaseContentNotFound("标签不存在")
            connection.execute(
                "DELETE FROM tags WHERE id=? AND profile_id=?",
                (tag_id, profile_id),
            )
            return {
                "id": row["id"],
                "name": row["name"],
                "memory_count": int(row["memory_count"] or 0),
                "deleted": True,
            }

    def attach_memory_tag(
        self, *, profile_id: str, memory_id: str, tag_id: str, timestamp: str
    ) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO memory_tags(memory_id, tag_id, created_at)
                SELECT ?, ?, ?
                WHERE EXISTS (
                    SELECT 1 FROM memories
                    WHERE id=? AND profile_id=? AND deleted_at IS NULL
                )
                AND EXISTS (
                    SELECT 1 FROM tags
                    WHERE id=? AND profile_id=?
                )
                """,
                (memory_id, tag_id, timestamp, memory_id, profile_id, tag_id, profile_id),
            )
            if cursor.rowcount:
                return True
            existing = connection.execute(
                """
                SELECT 1
                FROM memory_tags mt
                JOIN memories m ON m.id=mt.memory_id
                JOIN tags t ON t.id=mt.tag_id
                WHERE mt.memory_id=? AND mt.tag_id=?
                  AND m.profile_id=? AND t.profile_id=?
                  AND m.deleted_at IS NULL
                """,
                (memory_id, tag_id, profile_id, profile_id),
            ).fetchone()
            return existing is not None

    def detach_memory_tag(self, *, profile_id: str, memory_id: str, tag_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM memory_tags
                WHERE memory_id=? AND tag_id=?
                  AND EXISTS (
                      SELECT 1 FROM memories
                      WHERE memories.id=memory_tags.memory_id
                        AND memories.profile_id=?
                        AND memories.deleted_at IS NULL
                  )
                  AND EXISTS (
                      SELECT 1 FROM tags
                      WHERE tags.id=memory_tags.tag_id
                        AND tags.profile_id=?
                  )
                """,
                (memory_id, tag_id, profile_id, profile_id),
            )
            return bool(cursor.rowcount)

    def list_memory_tags(self, *, profile_id: str, memory_id: str) -> list[dict[str, Any]]:
        return self.list_memory_tags_for_memories(
            profile_id=profile_id, memory_ids=[memory_id]
        ).get(memory_id, [])

    def list_memory_tags_for_memories(
        self, *, profile_id: str, memory_ids: list[str]
    ) -> dict[str, list[dict[str, Any]]]:
        unique_ids = list(dict.fromkeys(memory_ids))
        if not unique_ids:
            return {}
        placeholders = ",".join("?" for _ in unique_ids)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT mt.memory_id, t.id, t.name, t.color
                FROM tags t
                JOIN memory_tags mt ON mt.tag_id=t.id
                JOIN memories m ON m.id=mt.memory_id
                WHERE mt.memory_id IN ({placeholders})
                  AND m.profile_id=? AND t.profile_id=?
                  AND m.deleted_at IS NULL
                ORDER BY mt.memory_id, t.name
                """,
                (*unique_ids, profile_id, profile_id),
            ).fetchall()
        result = {memory_id: [] for memory_id in unique_ids}
        for row in rows:
            result[row["memory_id"]].append(
                {"id": row["id"], "name": row["name"], "color": row["color"]}
            )
        return result
