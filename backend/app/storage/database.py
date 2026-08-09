from __future__ import annotations

import html
import re
import sqlite3
from calendar import monthrange
from pathlib import Path
from typing import Any

from app.security.crypto import decrypt_json, encrypt_json


LATEST_SCHEMA_VERSION = 7
PROFILE_AAD = b"lifegraph:v1:profile"
EVENT_AAD_PREFIX = b"lifegraph:v2:event:"
MEMORY_AAD_PREFIX = b"lifegraph:v2:memory:"
PLAN_AAD_PREFIX = b"lifegraph:v2:plan:"
ATTACHMENT_META_AAD_PREFIX = b"lifegraph:v1:attachment-meta:"

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

    def _ensure_material_attachment_schema(self, connection: sqlite3.Connection) -> None:
        """Upgrade attachments so a material may exist without a parent content item.

        v6 required every encrypted file to belong to an event/memory/plan. v7
        keeps that relation optional: a row with NULL kind/content_id is an
        independent material that still has its own encrypted metadata and
        timeline relationship.
        """
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='attachments'"
        ).fetchone()
        if row is None:
            return
        columns = {item["name"]: item for item in connection.execute("PRAGMA table_info(attachments)")}
        kind = columns.get("kind")
        content_id = columns.get("content_id")
        needs_upgrade = bool(
            (kind and int(kind["notnull"]) == 1)
            or (content_id and int(content_id["notnull"]) == 1)
            or "CHECK(kind IN ('event', 'memory', 'plan'))" in str(row["sql"] or "")
        )
        if not needs_upgrade:
            return

        connection.execute("DROP INDEX IF EXISTS idx_attachments_content")
        connection.execute("DROP INDEX IF EXISTS idx_attachments_profile")
        connection.execute("DROP TABLE IF EXISTS attachments_v7")
        connection.execute(
            """
            CREATE TABLE attachments_v7 (
                id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL,
                kind TEXT CHECK(kind IS NULL OR kind IN ('event', 'memory', 'plan')),
                content_id TEXT,
                file_nonce BLOB NOT NULL,
                metadata_nonce BLOB NOT NULL,
                metadata_ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                CHECK((kind IS NULL AND content_id IS NULL) OR (kind IS NOT NULL AND content_id IS NOT NULL))
            )
            """
        )
        connection.execute(
            """
            INSERT INTO attachments_v7(
                id, profile_id, kind, content_id, file_nonce, metadata_nonce,
                metadata_ciphertext, created_at, updated_at
            )
            SELECT id, profile_id, kind, content_id, file_nonce, metadata_nonce,
                   metadata_ciphertext, created_at, updated_at
            FROM attachments
            """
        )
        connection.execute("DROP TABLE attachments")
        connection.execute("ALTER TABLE attachments_v7 RENAME TO attachments")
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_attachments_content
            ON attachments(profile_id, kind, content_id, created_at)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_attachments_profile
            ON attachments(profile_id, created_at)
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

                CREATE TABLE IF NOT EXISTS content_tags (
                    kind TEXT NOT NULL CHECK(kind IN ('event', 'memory', 'plan')),
                    content_id TEXT NOT NULL,
                    tag_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(kind, content_id, tag_id),
                    FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_tags_profile
                ON tags(profile_id, name);

                CREATE INDEX IF NOT EXISTS idx_memory_tags_memory
                ON memory_tags(memory_id);

                CREATE INDEX IF NOT EXISTS idx_content_tags_content
                ON content_tags(kind, content_id);

                CREATE INDEX IF NOT EXISTS idx_content_tags_tag
                ON content_tags(tag_id, kind);


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
                
                CREATE TABLE IF NOT EXISTS attachments (
                    id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    kind TEXT CHECK(kind IS NULL OR kind IN ('event', 'memory', 'plan')),
                    content_id TEXT,
                    file_nonce BLOB NOT NULL,
                    metadata_nonce BLOB NOT NULL,
                    metadata_ciphertext BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                    CHECK((kind IS NULL AND content_id IS NULL) OR (kind IS NOT NULL AND content_id IS NOT NULL))
                );

                CREATE INDEX IF NOT EXISTS idx_attachments_content
                ON attachments(profile_id, kind, content_id, created_at);

                CREATE INDEX IF NOT EXISTS idx_attachments_profile
                ON attachments(profile_id, created_at);
                """
            )
            self._ensure_material_attachment_schema(connection)
            for table, date_column, _ in _CONTENT_TABLES.values():
                connection.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_{table}_profile_date
                    ON {table}(profile_id, {date_column})
                    WHERE deleted_at IS NULL
                    """
                )
                self._ensure_period_columns(connection, table, date_column)

            # v5: migrate existing memory-only tag links into the unified relation.
            connection.execute(
                """
                INSERT OR IGNORE INTO content_tags(kind, content_id, tag_id, created_at)
                SELECT 'memory', memory_id, tag_id, created_at FROM memory_tags
                """
            )
            # The legacy relation must be drained after migration; otherwise a tag
            # detached in v5 would be copied back into content_tags on the next startup.
            connection.execute("DELETE FROM memory_tags")

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

            attachment_rows = connection.execute(
                "SELECT id, metadata_nonce, metadata_ciphertext FROM attachments"
            ).fetchall()
            for row in attachment_rows:
                decrypt_json(
                    master_key,
                    row["metadata_nonce"],
                    row["metadata_ciphertext"],
                    aad=self._aad(ATTACHMENT_META_AAD_PREFIX, row["id"]),
                )
            counts["attachment"] = len(attachment_rows)
            verified_records += len(attachment_rows)

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
        kind: str | None,
        content_id: str | None,
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

    def move_content_period(
        self,
        *,
        kind: str,
        content_id: str,
        profile_id: str,
        anchor_date: str,
        time_scope: str,
        period_key: str,
        expected_revision: int,
        timestamp: str,
    ) -> dict[str, Any]:
        if kind not in _CONTENT_TABLES:
            raise ValueError("不支持的内容类型")
        table, date_column, _aad_prefix = _CONTENT_TABLES[kind]
        with self.connect() as connection:
            cursor = connection.execute(
                f"""
                UPDATE {table}
                SET {date_column}=?, time_scope=?, period_key=?,
                    updated_at=?, revision=revision + 1
                WHERE id=? AND profile_id=? AND deleted_at IS NULL AND revision=?
                """,
                (
                    anchor_date,
                    time_scope,
                    period_key,
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
                SELECT id, {date_column}, time_scope, period_key, updated_at, revision
                FROM {table}
                WHERE id=? AND profile_id=?
                """,
                (content_id, profile_id),
            ).fetchone()
        if row is None:
            raise DatabaseContentNotFound("内容不存在或已经被删除")
        return {
            "kind": kind,
            "id": row["id"],
            "anchor_date": row[date_column],
            "time_scope": row["time_scope"],
            "period_key": row["period_key"],
            "updated_at": row["updated_at"],
            "revision": row["revision"],
            "moved": True,
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
            attachment_ids = [
                item["id"]
                for item in connection.execute(
                    "SELECT id FROM attachments WHERE profile_id=? AND kind=? AND content_id=?",
                    (profile_id, kind, content_id),
                ).fetchall()
            ]
            connection.execute(
                "DELETE FROM content_tags WHERE kind=? AND content_id=?",
                (kind, content_id),
            )
            connection.execute(
                "DELETE FROM attachments WHERE profile_id=? AND kind=? AND content_id=?",
                (profile_id, kind, content_id),
            )
            connection.execute(
                f"DELETE FROM {table} WHERE id=? AND profile_id=? AND deleted_at IS NOT NULL",
                (content_id, profile_id),
            )
        return {
            "kind": kind,
            "id": content_id,
            "permanently_deleted": True,
            "attachment_ids": attachment_ids,
        }

    def empty_trash(self, *, profile_id: str) -> dict[str, Any]:
        counts: dict[str, int] = {}
        attachment_ids: list[str] = []
        with self.connect() as connection:
            for kind, (table, _, _) in _CONTENT_TABLES.items():
                deleted_ids = [
                    row["id"]
                    for row in connection.execute(
                        f"SELECT id FROM {table} WHERE profile_id=? AND deleted_at IS NOT NULL",
                        (profile_id,),
                    ).fetchall()
                ]
                if deleted_ids:
                    placeholders = ",".join("?" for _ in deleted_ids)
                    attachment_ids.extend(
                        row["id"]
                        for row in connection.execute(
                            f"""
                            SELECT id FROM attachments
                            WHERE profile_id=? AND kind=? AND content_id IN ({placeholders})
                            """,
                            (profile_id, kind, *deleted_ids),
                        ).fetchall()
                    )
                connection.execute(
                    f"""
                    DELETE FROM content_tags
                    WHERE kind=? AND content_id IN (
                        SELECT id FROM {table} WHERE profile_id=? AND deleted_at IS NOT NULL
                    )
                    """,
                    (kind, profile_id),
                )
                connection.execute(
                    f"""
                    DELETE FROM attachments
                    WHERE profile_id=? AND kind=? AND content_id IN (
                        SELECT id FROM {table} WHERE profile_id=? AND deleted_at IS NOT NULL
                    )
                    """,
                    (profile_id, kind, profile_id),
                )
                cursor = connection.execute(
                    f"DELETE FROM {table} WHERE profile_id=? AND deleted_at IS NOT NULL",
                    (profile_id,),
                )
                counts[kind] = cursor.rowcount
        return {
            "counts": counts,
            "total": sum(counts.values()),
            "emptied": True,
            "attachment_ids": attachment_ids,
        }

    def content_exists(
        self,
        *,
        profile_id: str,
        kind: str,
        content_id: str,
        include_deleted: bool = False,
    ) -> bool:
        if kind not in _CONTENT_TABLES:
            return False
        table, _, _ = _CONTENT_TABLES[kind]
        deleted_clause = "" if include_deleted else " AND deleted_at IS NULL"
        with self.connect() as connection:
            row = connection.execute(
                f"SELECT 1 FROM {table} WHERE id=? AND profile_id=?{deleted_clause}",
                (content_id, profile_id),
            ).fetchone()
        return row is not None

    def get_content_reference(
        self,
        master_key: bytes,
        *,
        profile_id: str,
        kind: str,
        content_id: str,
        include_deleted: bool = False,
    ) -> dict[str, Any]:
        if kind not in _CONTENT_TABLES:
            raise DatabaseContentNotFound("内容不存在")
        table, date_column, aad_prefix = _CONTENT_TABLES[kind]
        deleted_clause = "" if include_deleted else " AND deleted_at IS NULL"
        with self.connect() as connection:
            row = connection.execute(
                f"""
                SELECT id, profile_id, {date_column}, time_scope, period_key,
                       nonce, ciphertext, created_at, updated_at, revision, deleted_at
                FROM {table}
                WHERE id=? AND profile_id=?{deleted_clause}
                """,
                (content_id, profile_id),
            ).fetchone()
        if row is None:
            raise DatabaseContentNotFound("内容不存在或已经被删除")
        payload = decrypt_json(
            master_key,
            row["nonce"],
            row["ciphertext"],
            aad=self._aad(aad_prefix, row["id"]),
        )
        return {
            "id": row["id"],
            "kind": kind,
            "profile_id": row["profile_id"],
            date_column: row[date_column],
            "time_scope": row["time_scope"],
            "period_key": row["period_key"],
            "title": payload.get("title") or "未命名内容",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "revision": row["revision"],
            "deleted_at": row["deleted_at"],
        }

    def create_attachment(
        self,
        master_key: bytes,
        *,
        attachment_id: str,
        profile_id: str,
        kind: str | None,
        content_id: str | None,
        file_nonce: bytes,
        metadata: dict[str, Any],
        timestamp: str,
    ) -> dict[str, Any]:
        if (kind is None) != (content_id is None):
            raise ValueError("资料关联必须同时包含内容类型和内容 ID")
        if kind is not None:
            if kind not in _CONTENT_TABLES:
                raise ValueError("不支持的内容类型")
            if not self.content_exists(
                profile_id=profile_id, kind=kind, content_id=content_id or "", include_deleted=False
            ):
                raise DatabaseContentNotFound("内容不存在或已经被删除")
        metadata_nonce, metadata_ciphertext = encrypt_json(
            master_key,
            metadata,
            aad=self._aad(ATTACHMENT_META_AAD_PREFIX, attachment_id),
        )
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO attachments(
                    id, profile_id, kind, content_id, file_nonce,
                    metadata_nonce, metadata_ciphertext, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attachment_id,
                    profile_id,
                    kind,
                    content_id,
                    file_nonce,
                    metadata_nonce,
                    metadata_ciphertext,
                    timestamp,
                    timestamp,
                ),
            )
        return {
            "id": attachment_id,
            "profile_id": profile_id,
            "kind": kind,
            "content_id": content_id,
            **metadata,
            "created_at": timestamp,
            "updated_at": timestamp,
        }

    def update_attachment_metadata(
        self,
        master_key: bytes,
        *,
        profile_id: str,
        attachment_id: str,
        metadata: dict[str, Any],
        timestamp: str,
    ) -> dict[str, Any]:
        metadata_nonce, metadata_ciphertext = encrypt_json(
            master_key,
            metadata,
            aad=self._aad(ATTACHMENT_META_AAD_PREFIX, attachment_id),
        )
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE attachments
                SET metadata_nonce=?, metadata_ciphertext=?, updated_at=?
                WHERE id=? AND profile_id=?
                """,
                (metadata_nonce, metadata_ciphertext, timestamp, attachment_id, profile_id),
            )
            if cursor.rowcount != 1:
                raise DatabaseContentNotFound("附件不存在")
            row = connection.execute(
                """
                SELECT id, profile_id, kind, content_id, file_nonce, created_at, updated_at
                FROM attachments
                WHERE id=? AND profile_id=?
                """,
                (attachment_id, profile_id),
            ).fetchone()
        if row is None:
            raise DatabaseContentNotFound("附件不存在")
        return {
            "id": row["id"],
            "profile_id": row["profile_id"],
            "kind": row["kind"],
            "content_id": row["content_id"],
            "file_nonce": row["file_nonce"],
            **metadata,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_attachment_counts_for_items(
        self,
        *,
        profile_id: str,
        kind: str,
        content_ids: list[str],
    ) -> dict[str, int]:
        if kind not in _CONTENT_TABLES:
            raise ValueError("不支持的内容类型")
        normalized_ids = list(dict.fromkeys(content_id for content_id in content_ids if content_id))
        if not normalized_ids:
            return {}
        placeholders = ",".join("?" for _ in normalized_ids)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT content_id, COUNT(*) AS attachment_count
                FROM attachments
                WHERE profile_id=? AND kind=? AND content_id IN ({placeholders})
                GROUP BY content_id
                """,
                (profile_id, kind, *normalized_ids),
            ).fetchall()
        return {row["content_id"]: int(row["attachment_count"]) for row in rows}

    def list_attachments(
        self,
        master_key: bytes,
        *,
        profile_id: str,
        kind: str,
        content_id: str,
    ) -> list[dict[str, Any]]:
        if not self.content_exists(
            profile_id=profile_id, kind=kind, content_id=content_id, include_deleted=True
        ):
            raise DatabaseContentNotFound("内容不存在")
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, profile_id, kind, content_id, file_nonce,
                       metadata_nonce, metadata_ciphertext, created_at, updated_at
                FROM attachments
                WHERE profile_id=? AND kind=? AND content_id=?
                ORDER BY created_at ASC, id ASC
                """,
                (profile_id, kind, content_id),
            ).fetchall()
        values: list[dict[str, Any]] = []
        for row in rows:
            metadata = decrypt_json(
                master_key,
                row["metadata_nonce"],
                row["metadata_ciphertext"],
                aad=self._aad(ATTACHMENT_META_AAD_PREFIX, row["id"]),
            )
            values.append(
                {
                    "id": row["id"],
                    "profile_id": row["profile_id"],
                    "kind": row["kind"],
                    "content_id": row["content_id"],
                    "file_nonce": row["file_nonce"],
                    **metadata,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        return values

    def get_attachment(
        self,
        master_key: bytes,
        *,
        profile_id: str,
        attachment_id: str,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id, profile_id, kind, content_id, file_nonce,
                       metadata_nonce, metadata_ciphertext, created_at, updated_at
                FROM attachments
                WHERE id=? AND profile_id=?
                """,
                (attachment_id, profile_id),
            ).fetchone()
        if row is None:
            raise DatabaseContentNotFound("附件不存在")
        metadata = decrypt_json(
            master_key,
            row["metadata_nonce"],
            row["metadata_ciphertext"],
            aad=self._aad(ATTACHMENT_META_AAD_PREFIX, row["id"]),
        )
        return {
            "id": row["id"],
            "profile_id": row["profile_id"],
            "kind": row["kind"],
            "content_id": row["content_id"],
            "file_nonce": row["file_nonce"],
            **metadata,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def delete_attachment(
        self,
        *,
        profile_id: str,
        kind: str,
        content_id: str,
        attachment_id: str,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id FROM attachments
                WHERE id=? AND profile_id=? AND kind=? AND content_id=?
                """,
                (attachment_id, profile_id, kind, content_id),
            ).fetchone()
            if row is None:
                raise DatabaseContentNotFound("附件不存在")
            connection.execute(
                "DELETE FROM attachments WHERE id=? AND profile_id=?",
                (attachment_id, profile_id),
            )
        return {"id": attachment_id, "deleted": True}

    def delete_independent_material(
        self,
        *,
        profile_id: str,
        attachment_id: str,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id, kind, content_id FROM attachments
                WHERE id=? AND profile_id=?
                """,
                (attachment_id, profile_id),
            ).fetchone()
            if row is None:
                raise DatabaseContentNotFound("资料不存在")
            if row["kind"] is not None or row["content_id"] is not None:
                raise DatabaseContentNotFound("该资料仍属于内容附件，不能作为独立资料删除")
            connection.execute(
                "DELETE FROM attachments WHERE id=? AND profile_id=?",
                (attachment_id, profile_id),
            )
        return {"id": attachment_id, "deleted": True}

    def iter_all_attachments(
        self,
        master_key: bytes,
        *,
        profile_id: str | None = None,
        batch_size: int = 256,
    ):
        """Yield decrypted attachment metadata in bounded batches.

        Attachment metadata remains encrypted at rest, so broad material searches
        still need to decrypt candidate rows. Iterating prevents a large library
        from materializing every decrypted metadata record in memory at once.
        """
        query = """
            SELECT id, profile_id, kind, content_id, file_nonce,
                   metadata_nonce, metadata_ciphertext, created_at, updated_at
            FROM attachments
        """
        params: tuple[Any, ...] = ()
        if profile_id is not None:
            query += " WHERE profile_id=?"
            params = (profile_id,)
        query += " ORDER BY created_at ASC, id ASC"
        with self.connect() as connection:
            cursor = connection.execute(query, params)
            while True:
                rows = cursor.fetchmany(max(1, int(batch_size)))
                if not rows:
                    break
                for row in rows:
                    metadata = decrypt_json(
                        master_key,
                        row["metadata_nonce"],
                        row["metadata_ciphertext"],
                        aad=self._aad(ATTACHMENT_META_AAD_PREFIX, row["id"]),
                    )
                    yield {
                        "id": row["id"],
                        "profile_id": row["profile_id"],
                        "kind": row["kind"],
                        "content_id": row["content_id"],
                        "file_nonce": row["file_nonce"],
                        **metadata,
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }

    def list_all_attachments(
        self,
        master_key: bytes,
        *,
        profile_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return list(self.iter_all_attachments(master_key, profile_id=profile_id))

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

    @staticmethod
    def _content_period_bounds(time_scope: str, period_key: str, anchor_date: str) -> tuple[str, str]:
        scope = time_scope or "day"
        key = period_key or anchor_date
        if scope == "year":
            return f"{key[:4]}-01-01", f"{key[:4]}-12-31"
        if scope == "month":
            year, month = (int(part) for part in key[:7].split("-"))
            last_day = monthrange(year, month)[1]
            return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"
        return key[:10], key[:10]

    def browse_content(
        self,
        master_key: bytes,
        *,
        profile_id: str,
        kinds: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort: str = "date_desc",
        limit: int = 100,
    ) -> dict[str, Any]:
        selected_kinds = list(dict.fromkeys(kinds or list(_CONTENT_TABLES)))
        selected_kinds = [kind for kind in selected_kinds if kind in _CONTENT_TABLES]
        if not selected_kinds:
            selected_kinds = list(_CONTENT_TABLES)

        values: list[dict[str, Any]] = []
        for kind in selected_kinds:
            table, date_column, aad_prefix = _CONTENT_TABLES[kind]
            with self.connect() as connection:
                rows = connection.execute(
                    f"""
                    SELECT id, profile_id, {date_column}, time_scope, period_key,
                           nonce, ciphertext, created_at, updated_at, revision
                    FROM {table}
                    WHERE profile_id=? AND deleted_at IS NULL
                    """,
                    (profile_id,),
                ).fetchall()

            for row in rows:
                period_start, period_end = self._content_period_bounds(
                    row["time_scope"], row["period_key"], row[date_column]
                )
                if date_from and period_end < date_from:
                    continue
                if date_to and period_start > date_to:
                    continue
                payload = decrypt_json(
                    master_key,
                    row["nonce"],
                    row["ciphertext"],
                    aad=self._aad(aad_prefix, row["id"]),
                )
                values.append(
                    {
                        "id": row["id"],
                        "kind": kind,
                        "profile_id": row["profile_id"],
                        "anchor_date": row[date_column],
                        date_column: row[date_column],
                        "time_scope": row["time_scope"],
                        "period_key": row["period_key"],
                        **payload,
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                        "revision": row["revision"],
                    }
                )

        if sort == "date_asc":
            values.sort(key=lambda item: (item["anchor_date"], item["created_at"], item["id"]))
        elif sort == "updated_desc":
            values.sort(
                key=lambda item: (item["updated_at"], item["anchor_date"], item["id"]),
                reverse=True,
            )
        else:
            values.sort(
                key=lambda item: (item["anchor_date"], item["created_at"], item["id"]),
                reverse=True,
            )

        total = len(values)
        counts = {kind: 0 for kind in _CONTENT_TABLES}
        for item in values:
            counts[item["kind"]] += 1

        has_more = total > limit
        page = values[:limit]
        for kind in _CONTENT_TABLES:
            content_ids = [item["id"] for item in page if item["kind"] == kind]
            tags_by_content = self.list_content_tags_for_items(
                profile_id=profile_id, kind=kind, content_ids=content_ids
            )
            for item in page:
                if item["kind"] == kind:
                    item["tags"] = tags_by_content.get(item["id"], [])

        return {
            "items": page,
            "count": len(page),
            "total": total,
            "counts": counts,
            "has_more": has_more,
        }

    def search_content(
        self,
        master_key: bytes,
        *,
        profile_id: str,
        query: str = "",
        kinds: list[str] | None = None,
        tag_ids: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort: str = "date_desc",
        limit: int = 100,
    ) -> dict[str, Any]:
        selected_kinds = list(dict.fromkeys(kinds or list(_CONTENT_TABLES)))
        selected_kinds = [kind for kind in selected_kinds if kind in _CONTENT_TABLES]
        if not selected_kinds:
            selected_kinds = list(_CONTENT_TABLES)

        tag_ids = list(dict.fromkeys(tag_ids or []))
        normalized_query = query.strip().casefold()
        values: list[dict[str, Any]] = []

        for kind in selected_kinds:
            table, date_column, aad_prefix = _CONTENT_TABLES[kind]
            where = [f"c.profile_id=?", "c.deleted_at IS NULL"]
            params: list[Any] = [profile_id]
            if tag_ids:
                placeholders = ",".join("?" for _ in tag_ids)
                where.append(
                    f"""
                    c.id IN (
                        SELECT ct.content_id
                        FROM content_tags ct
                        JOIN tags t ON t.id=ct.tag_id
                        WHERE ct.kind=? AND t.profile_id=? AND ct.tag_id IN ({placeholders})
                        GROUP BY ct.content_id
                        HAVING COUNT(DISTINCT ct.tag_id)=?
                    )
                    """
                )
                params.extend([kind, profile_id, *tag_ids, len(tag_ids)])

            with self.connect() as connection:
                rows = connection.execute(
                    f"""
                    SELECT c.id, c.profile_id, c.{date_column}, c.time_scope, c.period_key,
                           c.nonce, c.ciphertext, c.created_at, c.updated_at, c.revision
                    FROM {table} c
                    WHERE {' AND '.join(where)}
                    """,
                    params,
                ).fetchall()

            for row in rows:
                period_start, period_end = self._content_period_bounds(
                    row["time_scope"], row["period_key"], row[date_column]
                )
                if date_from and period_end < date_from:
                    continue
                if date_to and period_start > date_to:
                    continue

                payload = decrypt_json(
                    master_key,
                    row["nonce"],
                    row["ciphertext"],
                    aad=self._aad(aad_prefix, row["id"]),
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
                        "kind": kind,
                        "profile_id": row["profile_id"],
                        "anchor_date": row[date_column],
                        date_column: row[date_column],
                        "time_scope": row["time_scope"],
                        "period_key": row["period_key"],
                        **payload,
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                        "revision": row["revision"],
                    }
                )

        if sort == "date_asc":
            values.sort(key=lambda item: (item["anchor_date"], item["created_at"], item["id"]))
        elif sort == "updated_desc":
            values.sort(
                key=lambda item: (item["updated_at"], item["anchor_date"], item["id"]),
                reverse=True,
            )
        else:
            values.sort(
                key=lambda item: (item["anchor_date"], item["created_at"], item["id"]),
                reverse=True,
            )
        total = len(values)
        counts = {kind: 0 for kind in _CONTENT_TABLES}
        for item in values:
            counts[item["kind"]] += 1

        page = values[:limit]
        for kind in _CONTENT_TABLES:
            content_ids = [item["id"] for item in page if item["kind"] == kind]
            tags_by_content = self.list_content_tags_for_items(
                profile_id=profile_id, kind=kind, content_ids=content_ids
            )
            for item in page:
                if item["kind"] == kind:
                    item["tags"] = tags_by_content.get(item["id"], [])

        return {
            "items": page,
            "count": len(page),
            "total": total,
            "counts": counts,
            "has_more": total > limit,
        }

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
        return self.search_content(
            master_key,
            profile_id=profile_id,
            query=query,
            kinds=["memory"],
            tag_ids=tag_ids,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )

    def get_content_tag_map(
        self,
        *,
        profile_id: str,
        tag_ids: list[str],
        start_date: str,
        end_date: str,
        kinds: list[str] | None = None,
    ) -> dict[str, Any]:
        tag_ids = list(dict.fromkeys(tag_ids))
        selected_kinds = list(dict.fromkeys(kinds or list(_CONTENT_TABLES)))
        selected_kinds = [kind for kind in selected_kinds if kind in _CONTENT_TABLES]
        if not selected_kinds:
            selected_kinds = list(_CONTENT_TABLES)

        result: dict[str, Any] = {
            "dates": [],
            "months": [],
            "years": [],
            "content_count": 0,
            "counts": {kind: 0 for kind in _CONTENT_TABLES},
        }
        if not tag_ids:
            return result

        placeholders = ",".join("?" for _ in tag_ids)
        dates: set[str] = set()
        months: set[str] = set()
        years: set[str] = set()
        visible_ids: set[tuple[str, str]] = set()

        for kind in selected_kinds:
            table, date_column, _ = _CONTENT_TABLES[kind]
            with self.connect() as connection:
                rows = connection.execute(
                    f"""
                    SELECT c.id, c.{date_column} AS anchor_date, c.time_scope, c.period_key
                    FROM {table} c
                    JOIN content_tags ct ON ct.content_id=c.id AND ct.kind=?
                    JOIN tags t ON t.id=ct.tag_id
                    WHERE c.profile_id=? AND t.profile_id=?
                      AND c.deleted_at IS NULL
                      AND ct.tag_id IN ({placeholders})
                    GROUP BY c.id, c.{date_column}, c.time_scope, c.period_key
                    HAVING COUNT(DISTINCT ct.tag_id)=?
                    ORDER BY c.{date_column}, c.created_at, c.id
                    """,
                    (kind, profile_id, profile_id, *tag_ids, len(tag_ids)),
                ).fetchall()

            for row in rows:
                scope = row["time_scope"] or "day"
                key = row["period_key"] or row["anchor_date"]
                period_start, period_end = self._content_period_bounds(
                    scope, key, row["anchor_date"]
                )
                if period_end < start_date or period_start > end_date:
                    continue

                marker = (kind, row["id"])
                if marker not in visible_ids:
                    visible_ids.add(marker)
                    result["counts"][kind] += 1

                if scope == "day":
                    day_key = key[:10]
                    dates.add(day_key)
                    months.add(day_key[:7])
                    years.add(day_key[:4])
                elif scope == "month":
                    month_key = key[:7]
                    months.add(month_key)
                    years.add(month_key[:4])
                elif scope == "year":
                    years.add(key[:4])

        result["dates"] = sorted(dates)
        result["months"] = sorted(months)
        result["years"] = sorted(years)
        result["content_count"] = len(visible_ids)
        return result

    def get_memory_tag_map(
        self,
        *,
        profile_id: str,
        tag_ids: list[str],
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        result = self.get_content_tag_map(
            profile_id=profile_id,
            tag_ids=tag_ids,
            start_date=start_date,
            end_date=end_date,
            kinds=["memory"],
        )
        result["memory_count"] = result["counts"]["memory"]
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


    def _tag_counts_for_row(self, connection: sqlite3.Connection, *, profile_id: str, tag_id: str) -> dict[str, int]:
        counts = {"event_count": 0, "memory_count": 0, "plan_count": 0}
        for kind, (table, _, _) in _CONTENT_TABLES.items():
            row = connection.execute(
                f"""
                SELECT COUNT(DISTINCT ct.content_id) AS count
                FROM content_tags ct
                JOIN {table} c ON c.id=ct.content_id
                WHERE ct.kind=? AND ct.tag_id=?
                  AND c.profile_id=? AND c.deleted_at IS NULL
                """,
                (kind, tag_id, profile_id),
            ).fetchone()
            counts[f"{kind}_count"] = int(row["count"] or 0)
        counts["total_count"] = sum(counts.values())
        return counts

    def _tag_row(self, connection: sqlite3.Connection, *, profile_id: str, tag_id: str) -> dict[str, Any] | None:
        row = connection.execute(
            """
            SELECT id, name, color, created_at, updated_at
            FROM tags
            WHERE id=? AND profile_id=?
            """,
            (tag_id, profile_id),
        ).fetchone()
        if row is None:
            return None
        value = dict(row)
        value.update(self._tag_counts_for_row(connection, profile_id=profile_id, tag_id=tag_id))
        return value

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
                "event_count": 0,
                "memory_count": 0,
                "plan_count": 0,
                "total_count": 0,
            }

    def list_tags(self, *, profile_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, color, created_at, updated_at
                FROM tags
                WHERE profile_id=?
                ORDER BY name COLLATE NOCASE, created_at, id
                """,
                (profile_id,),
            ).fetchall()
            values: list[dict[str, Any]] = []
            for row in rows:
                value = dict(row)
                value.update(self._tag_counts_for_row(connection, profile_id=profile_id, tag_id=row["id"]))
                values.append(value)
            return values

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
            row = self._tag_row(connection, profile_id=profile_id, tag_id=tag_id)
            if row is None:  # pragma: no cover - defensive
                raise DatabaseContentNotFound("标签不存在")
            return row

    def delete_tag(self, *, profile_id: str, tag_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = self._tag_row(connection, profile_id=profile_id, tag_id=tag_id)
            if row is None:
                raise DatabaseContentNotFound("标签不存在")
            connection.execute(
                "DELETE FROM tags WHERE id=? AND profile_id=?",
                (tag_id, profile_id),
            )
            return {
                "id": row["id"],
                "name": row["name"],
                "event_count": row["event_count"],
                "memory_count": row["memory_count"],
                "plan_count": row["plan_count"],
                "total_count": row["total_count"],
                "deleted": True,
            }

    def attach_content_tag(
        self,
        *,
        profile_id: str,
        kind: str,
        content_id: str,
        tag_id: str,
        timestamp: str,
    ) -> bool:
        if kind not in _CONTENT_TABLES:
            raise ValueError("不支持的内容类型")
        table, _, _ = _CONTENT_TABLES[kind]
        with self.connect() as connection:
            cursor = connection.execute(
                f"""
                INSERT OR IGNORE INTO content_tags(kind, content_id, tag_id, created_at)
                SELECT ?, ?, ?, ?
                WHERE EXISTS (
                    SELECT 1 FROM {table}
                    WHERE id=? AND profile_id=? AND deleted_at IS NULL
                )
                AND EXISTS (
                    SELECT 1 FROM tags
                    WHERE id=? AND profile_id=?
                )
                """,
                (kind, content_id, tag_id, timestamp, content_id, profile_id, tag_id, profile_id),
            )
            if cursor.rowcount:
                return True
            existing = connection.execute(
                f"""
                SELECT 1
                FROM content_tags ct
                JOIN {table} c ON c.id=ct.content_id
                JOIN tags t ON t.id=ct.tag_id
                WHERE ct.kind=? AND ct.content_id=? AND ct.tag_id=?
                  AND c.profile_id=? AND t.profile_id=?
                  AND c.deleted_at IS NULL
                """,
                (kind, content_id, tag_id, profile_id, profile_id),
            ).fetchone()
            return existing is not None

    def detach_content_tag(self, *, profile_id: str, kind: str, content_id: str, tag_id: str) -> bool:
        if kind not in _CONTENT_TABLES:
            raise ValueError("不支持的内容类型")
        table, _, _ = _CONTENT_TABLES[kind]
        with self.connect() as connection:
            cursor = connection.execute(
                f"""
                DELETE FROM content_tags
                WHERE kind=? AND content_id=? AND tag_id=?
                  AND EXISTS (
                      SELECT 1 FROM {table}
                      WHERE {table}.id=content_tags.content_id
                        AND {table}.profile_id=?
                        AND {table}.deleted_at IS NULL
                  )
                  AND EXISTS (
                      SELECT 1 FROM tags
                      WHERE tags.id=content_tags.tag_id
                        AND tags.profile_id=?
                  )
                """,
                (kind, content_id, tag_id, profile_id, profile_id),
            )
            return bool(cursor.rowcount)

    def replace_content_tags(
        self,
        *,
        profile_id: str,
        kind: str,
        content_id: str,
        tag_ids: list[str],
        timestamp: str,
    ) -> list[dict[str, Any]]:
        if kind not in _CONTENT_TABLES:
            raise ValueError("不支持的内容类型")
        table, _, _ = _CONTENT_TABLES[kind]
        desired_ids = list(dict.fromkeys(tag_ids))
        with self.connect() as connection:
            content_exists = connection.execute(
                f"""
                SELECT 1 FROM {table}
                WHERE id=? AND profile_id=? AND deleted_at IS NULL
                """,
                (content_id, profile_id),
            ).fetchone()
            if content_exists is None:
                raise DatabaseContentNotFound("内容不存在")

            if desired_ids:
                placeholders = ",".join("?" for _ in desired_ids)
                rows = connection.execute(
                    f"""
                    SELECT id FROM tags
                    WHERE profile_id=? AND id IN ({placeholders})
                    """,
                    (profile_id, *desired_ids),
                ).fetchall()
                valid_ids = {row["id"] for row in rows}
                if valid_ids != set(desired_ids):
                    raise DatabaseContentNotFound("标签不存在")

            connection.execute(
                "DELETE FROM content_tags WHERE kind=? AND content_id=?",
                (kind, content_id),
            )
            if desired_ids:
                connection.executemany(
                    """
                    INSERT INTO content_tags(kind, content_id, tag_id, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    [(kind, content_id, tag_id, timestamp) for tag_id in desired_ids],
                )

        return self.list_content_tags(profile_id=profile_id, kind=kind, content_id=content_id)

    def bulk_update_content_tags(
        self,
        *,
        profile_id: str,
        items: list[dict[str, str]],
        tag_ids: list[str],
        operation: str,
        timestamp: str,
    ) -> list[dict[str, Any]]:
        if operation not in {"add", "remove"}:
            raise ValueError("不支持的批量标签操作")

        unique_items: list[dict[str, str]] = []
        seen_items: set[tuple[str, str]] = set()
        for raw in items:
            kind = str(raw.get("kind") or "").strip()
            content_id = str(raw.get("content_id") or "").strip()
            if kind not in _CONTENT_TABLES or not content_id:
                raise DatabaseContentNotFound("内容不存在")
            key = (kind, content_id)
            if key in seen_items:
                continue
            seen_items.add(key)
            unique_items.append({"kind": kind, "content_id": content_id})

        desired_tag_ids = list(dict.fromkeys(tag_ids))
        if not unique_items:
            raise DatabaseContentNotFound("内容不存在")
        if not desired_tag_ids:
            raise DatabaseContentNotFound("标签不存在")

        with self.connect() as connection:
            tag_placeholders = ",".join("?" for _ in desired_tag_ids)
            tag_rows = connection.execute(
                f"""
                SELECT id FROM tags
                WHERE profile_id=? AND id IN ({tag_placeholders})
                """,
                (profile_id, *desired_tag_ids),
            ).fetchall()
            if {row["id"] for row in tag_rows} != set(desired_tag_ids):
                raise DatabaseContentNotFound("标签不存在")

            for item in unique_items:
                table, _, _ = _CONTENT_TABLES[item["kind"]]
                exists = connection.execute(
                    f"""
                    SELECT 1 FROM {table}
                    WHERE id=? AND profile_id=? AND deleted_at IS NULL
                    """,
                    (item["content_id"], profile_id),
                ).fetchone()
                if exists is None:
                    raise DatabaseContentNotFound("内容不存在")

            if operation == "add":
                connection.executemany(
                    """
                    INSERT OR IGNORE INTO content_tags(kind, content_id, tag_id, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        (item["kind"], item["content_id"], tag_id, timestamp)
                        for item in unique_items
                        for tag_id in desired_tag_ids
                    ],
                )
            else:
                delete_placeholders = ",".join("?" for _ in desired_tag_ids)
                for item in unique_items:
                    connection.execute(
                        f"""
                        DELETE FROM content_tags
                        WHERE kind=? AND content_id=? AND tag_id IN ({delete_placeholders})
                        """,
                        (item["kind"], item["content_id"], *desired_tag_ids),
                    )

        grouped: dict[str, list[str]] = {}
        for item in unique_items:
            grouped.setdefault(item["kind"], []).append(item["content_id"])
        tags_by_kind = {
            kind: self.list_content_tags_for_items(
                profile_id=profile_id, kind=kind, content_ids=content_ids
            )
            for kind, content_ids in grouped.items()
        }
        return [
            {
                "kind": item["kind"],
                "content_id": item["content_id"],
                "tags": tags_by_kind.get(item["kind"], {}).get(item["content_id"], []),
            }
            for item in unique_items
        ]

    def list_content_tags(self, *, profile_id: str, kind: str, content_id: str) -> list[dict[str, Any]]:
        return self.list_content_tags_for_items(
            profile_id=profile_id, kind=kind, content_ids=[content_id]
        ).get(content_id, [])

    def list_content_tags_for_items(
        self, *, profile_id: str, kind: str, content_ids: list[str]
    ) -> dict[str, list[dict[str, Any]]]:
        if kind not in _CONTENT_TABLES:
            raise ValueError("不支持的内容类型")
        unique_ids = list(dict.fromkeys(content_ids))
        if not unique_ids:
            return {}
        table, _, _ = _CONTENT_TABLES[kind]
        placeholders = ",".join("?" for _ in unique_ids)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT ct.content_id, t.id, t.name, t.color
                FROM tags t
                JOIN content_tags ct ON ct.tag_id=t.id
                JOIN {table} c ON c.id=ct.content_id
                WHERE ct.kind=? AND ct.content_id IN ({placeholders})
                  AND c.profile_id=? AND t.profile_id=?
                  AND c.deleted_at IS NULL
                ORDER BY ct.content_id, t.name COLLATE NOCASE, t.id
                """,
                (kind, *unique_ids, profile_id, profile_id),
            ).fetchall()
        result = {content_id: [] for content_id in unique_ids}
        for row in rows:
            result[row["content_id"]].append(
                {"id": row["id"], "name": row["name"], "color": row["color"]}
            )
        return result

    # Compatibility wrappers used by existing memory-specific search/filter APIs.
    def attach_memory_tag(self, *, profile_id: str, memory_id: str, tag_id: str, timestamp: str) -> bool:
        return self.attach_content_tag(
            profile_id=profile_id, kind="memory", content_id=memory_id, tag_id=tag_id, timestamp=timestamp
        )

    def detach_memory_tag(self, *, profile_id: str, memory_id: str, tag_id: str) -> bool:
        return self.detach_content_tag(
            profile_id=profile_id, kind="memory", content_id=memory_id, tag_id=tag_id
        )

    def list_memory_tags(self, *, profile_id: str, memory_id: str) -> list[dict[str, Any]]:
        return self.list_content_tags(profile_id=profile_id, kind="memory", content_id=memory_id)

    def list_memory_tags_for_memories(
        self, *, profile_id: str, memory_ids: list[str]
    ) -> dict[str, list[dict[str, Any]]]:
        return self.list_content_tags_for_items(
            profile_id=profile_id, kind="memory", content_ids=memory_ids
        )

