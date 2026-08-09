from __future__ import annotations

import html
import re
import sqlite3
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.security.crypto import decrypt_json, encrypt_json


LATEST_SCHEMA_VERSION = 11
PROFILE_AAD = b"lifegraph:v1:profile"
EVENT_AAD_PREFIX = b"lifegraph:v2:event:"
MEMORY_AAD_PREFIX = b"lifegraph:v2:memory:"
PLAN_AAD_PREFIX = b"lifegraph:v2:plan:"
ATTACHMENT_META_AAD_PREFIX = b"lifegraph:v1:attachment-meta:"
MATERIAL_SCAN_SOURCE_AAD_PREFIX = b"lifegraph:v1:material-scan-source:"

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

    def _ensure_attachment_storage_schema(self, connection: sqlite3.Connection) -> None:
        """Upgrade attachment storage descriptors for chunked large-media records.

        v8 keeps ordinary <=50 MB attachment blobs in the existing encrypted
        ``attachments`` store while allowing large media to reference an external
        encrypted chunk set under ``data/media``. Existing rows are migrated as
        ``blob-v1`` without changing their encrypted metadata or ciphertext files.
        """
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='attachments'"
        ).fetchone()
        if row is None:
            return
        columns = {item["name"]: item for item in connection.execute("PRAGMA table_info(attachments)")}
        storage_kind = columns.get("storage_kind")
        media_id = columns.get("media_id")
        file_nonce = columns.get("file_nonce")
        needs_upgrade = bool(
            storage_kind is None
            or media_id is None
            or (file_nonce and int(file_nonce["notnull"]) == 1)
        )
        if not needs_upgrade:
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_attachments_media_id
                ON attachments(media_id)
                WHERE media_id IS NOT NULL
                """
            )
            return

        connection.execute("DROP INDEX IF EXISTS idx_attachments_content")
        connection.execute("DROP INDEX IF EXISTS idx_attachments_profile")
        connection.execute("DROP INDEX IF EXISTS idx_attachments_media_id")
        connection.execute("DROP TABLE IF EXISTS attachments_v8")
        connection.execute(
            """
            CREATE TABLE attachments_v8 (
                id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL,
                kind TEXT CHECK(kind IS NULL OR kind IN ('event', 'memory', 'plan')),
                content_id TEXT,
                storage_kind TEXT NOT NULL DEFAULT 'blob-v1'
                    CHECK(storage_kind IN ('blob-v1', 'chunked-v1')),
                file_nonce BLOB,
                media_id TEXT,
                metadata_nonce BLOB NOT NULL,
                metadata_ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                CHECK((kind IS NULL AND content_id IS NULL) OR (kind IS NOT NULL AND content_id IS NOT NULL)),
                CHECK(
                    (storage_kind='blob-v1' AND file_nonce IS NOT NULL AND media_id IS NULL)
                    OR
                    (storage_kind='chunked-v1' AND file_nonce IS NULL AND media_id IS NOT NULL)
                )
            )
            """
        )
        existing_columns = set(columns)
        if {"storage_kind", "media_id"}.issubset(existing_columns):
            connection.execute(
                """
                INSERT INTO attachments_v8(
                    id, profile_id, kind, content_id, storage_kind, file_nonce, media_id,
                    metadata_nonce, metadata_ciphertext, created_at, updated_at
                )
                SELECT id, profile_id, kind, content_id,
                       COALESCE(NULLIF(storage_kind, ''), 'blob-v1'),
                       file_nonce, media_id,
                       metadata_nonce, metadata_ciphertext, created_at, updated_at
                FROM attachments
                """
            )
        else:
            connection.execute(
                """
                INSERT INTO attachments_v8(
                    id, profile_id, kind, content_id, storage_kind, file_nonce, media_id,
                    metadata_nonce, metadata_ciphertext, created_at, updated_at
                )
                SELECT id, profile_id, kind, content_id, 'blob-v1', file_nonce, NULL,
                       metadata_nonce, metadata_ciphertext, created_at, updated_at
                FROM attachments
                """
            )
        connection.execute("DROP TABLE attachments")
        connection.execute("ALTER TABLE attachments_v8 RENAME TO attachments")
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
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_attachments_media_id
            ON attachments(media_id)
            WHERE media_id IS NOT NULL
            """
        )

    @staticmethod
    def _timeline_offset(value: str | None) -> str | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            return "+00:00"
        match = re.search(r"([+-]\d{2}:\d{2})$", raw)
        return match.group(1) if match else None

    @classmethod
    def _attachment_timeline_columns(cls, metadata: dict[str, Any]) -> dict[str, Any]:
        """Return the non-sensitive, indexable timeline mirror for one attachment.

        Human-readable metadata remains encrypted.  These columns intentionally
        contain only normalized temporal facts needed for range queries and later
        timeline aggregation.  v8 rows are not decrypted during schema migration;
        they remain NULL until the dedicated v0.0.10.2 backfill runs.
        """
        timeline_at = str(metadata.get("timeline_at") or "").strip() or None
        source = str(
            metadata.get("time_source")
            or metadata.get("timeline_time_source")
            or ""
        ).strip() or None

        allowed_precision = {"year", "month", "day", "minute", "second", "unknown"}
        precision = str(metadata.get("time_precision") or "").strip().lower() or None
        if precision not in allowed_precision:
            if not timeline_at:
                precision = None
            elif source == "content:date" or re.fullmatch(r"\d{4}-\d{2}-\d{2}", timeline_at):
                precision = "day"
            elif re.fullmatch(r"\d{4}-\d{2}", timeline_at):
                precision = "month"
            elif re.fullmatch(r"\d{4}", timeline_at):
                precision = "year"
            elif re.search(r"T\d{2}:\d{2}(?:$|[+-])", timeline_at):
                precision = "minute"
            else:
                precision = "second"

        allowed_confidence = {"high", "medium", "low", "unknown"}
        confidence = str(metadata.get("time_confidence") or "").strip().lower() or None
        if confidence not in allowed_confidence:
            if not timeline_at:
                confidence = None
            elif source and source.startswith("exif:"):
                confidence = "high"
            elif source == "document:created":
                confidence = "high"
            elif source in {"document:modified", "file:last_modified", "content:date"}:
                confidence = "medium"
            elif source == "attachment:added":
                confidence = "low"
            elif source == "manual":
                confidence = "high"
            else:
                confidence = "unknown"

        timezone_offset = str(metadata.get("timezone_offset") or "").strip() or None
        if timezone_offset is None:
            timezone_offset = cls._timeline_offset(timeline_at)

        timeline_end_at = str(metadata.get("timeline_end_at") or "").strip() or None
        if timeline_end_at is None and timeline_at and precision in {"minute", "second"}:
            try:
                duration = float(metadata.get("duration_seconds"))
                if 0 < duration <= 366 * 24 * 3600:
                    parsed = datetime.fromisoformat(timeline_at.replace("Z", "+00:00"))
                    timeline_end_at = (parsed + timedelta(seconds=duration)).isoformat(timespec="seconds")
            except (TypeError, ValueError, OverflowError):
                timeline_end_at = None

        return {
            "timeline_at": timeline_at,
            "timeline_end_at": timeline_end_at,
            "time_precision": precision,
            "time_source": source,
            "time_confidence": confidence,
            "timezone_offset": timezone_offset,
        }

    def _ensure_attachment_timeline_schema(self, connection: sqlite3.Connection) -> None:
        """v9: add queryable timeline facts without decrypting existing metadata."""
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='attachments'"
        ).fetchone()
        if row is None:
            return
        columns = self._columns(connection, "attachments")
        additions = {
            "timeline_at": "TEXT",
            "timeline_end_at": "TEXT",
            "time_precision": "TEXT CHECK(time_precision IS NULL OR time_precision IN ('year','month','day','minute','second','unknown'))",
            "time_source": "TEXT",
            "time_confidence": "TEXT CHECK(time_confidence IS NULL OR time_confidence IN ('high','medium','low','unknown'))",
            "timezone_offset": "TEXT",
        }
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(f"ALTER TABLE attachments ADD COLUMN {name} {definition}")
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_attachments_profile_timeline
            ON attachments(profile_id, timeline_at, id)
            WHERE timeline_at IS NOT NULL
            """
        )

    def _ensure_attachment_timeline_stats_schema(self, connection: sqlite3.Connection) -> None:
        """v10: keep compact year/month/day/hour counts for the timeline UI.

        Creating the tables and triggers is cheap and happens during normal schema
        initialization. Existing v9 rows are deliberately *not* aggregated here;
        the first timeline-summary request rebuilds the statistics from the already
        queryable timeline mirror using SQL only (no metadata decryption).
        """
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS attachment_timeline_stats (
                profile_id TEXT NOT NULL,
                level TEXT NOT NULL CHECK(level IN ('year', 'month', 'day', 'hour')),
                period_key TEXT NOT NULL,
                total_count INTEGER NOT NULL DEFAULT 0 CHECK(total_count >= 0),
                PRIMARY KEY(profile_id, level, period_key),
                FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS attachment_timeline_stats_meta (
                profile_id TEXT PRIMARY KEY,
                built_at TEXT NOT NULL,
                FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_attachment_timeline_stats_lookup
            ON attachment_timeline_stats(profile_id, level, period_key);

            DROP TRIGGER IF EXISTS trg_attachments_timeline_stats_insert;
            CREATE TRIGGER trg_attachments_timeline_stats_insert
            AFTER INSERT ON attachments
            WHEN NEW.timeline_at IS NOT NULL
                 AND NEW.time_precision IS NOT NULL
                 AND NEW.time_precision != 'unknown'
            BEGIN
                INSERT OR IGNORE INTO attachment_timeline_stats(profile_id, level, period_key, total_count)
                VALUES(NEW.profile_id, 'year', substr(NEW.timeline_at, 1, 4), 0);
                UPDATE attachment_timeline_stats
                SET total_count=total_count+1
                WHERE profile_id=NEW.profile_id AND level='year'
                  AND period_key=substr(NEW.timeline_at, 1, 4);

                INSERT OR IGNORE INTO attachment_timeline_stats(profile_id, level, period_key, total_count)
                SELECT NEW.profile_id, 'month', substr(NEW.timeline_at, 1, 7), 0
                WHERE NEW.time_precision IN ('month', 'day', 'minute', 'second')
                  AND length(NEW.timeline_at) >= 7;
                UPDATE attachment_timeline_stats
                SET total_count=total_count+1
                WHERE profile_id=NEW.profile_id AND level='month'
                  AND period_key=substr(NEW.timeline_at, 1, 7)
                  AND NEW.time_precision IN ('month', 'day', 'minute', 'second')
                  AND length(NEW.timeline_at) >= 7;

                INSERT OR IGNORE INTO attachment_timeline_stats(profile_id, level, period_key, total_count)
                SELECT NEW.profile_id, 'day', substr(NEW.timeline_at, 1, 10), 0
                WHERE NEW.time_precision IN ('day', 'minute', 'second')
                  AND length(NEW.timeline_at) >= 10;
                UPDATE attachment_timeline_stats
                SET total_count=total_count+1
                WHERE profile_id=NEW.profile_id AND level='day'
                  AND period_key=substr(NEW.timeline_at, 1, 10)
                  AND NEW.time_precision IN ('day', 'minute', 'second')
                  AND length(NEW.timeline_at) >= 10;

                INSERT OR IGNORE INTO attachment_timeline_stats(profile_id, level, period_key, total_count)
                SELECT NEW.profile_id, 'hour', substr(NEW.timeline_at, 1, 13), 0
                WHERE NEW.time_precision IN ('minute', 'second')
                  AND length(NEW.timeline_at) >= 13;
                UPDATE attachment_timeline_stats
                SET total_count=total_count+1
                WHERE profile_id=NEW.profile_id AND level='hour'
                  AND period_key=substr(NEW.timeline_at, 1, 13)
                  AND NEW.time_precision IN ('minute', 'second')
                  AND length(NEW.timeline_at) >= 13;
            END;

            DROP TRIGGER IF EXISTS trg_attachments_timeline_stats_delete;
            CREATE TRIGGER trg_attachments_timeline_stats_delete
            AFTER DELETE ON attachments
            WHEN OLD.timeline_at IS NOT NULL
                 AND OLD.time_precision IS NOT NULL
                 AND OLD.time_precision != 'unknown'
            BEGIN
                UPDATE attachment_timeline_stats
                SET total_count=total_count-1
                WHERE profile_id=OLD.profile_id AND level='year'
                  AND period_key=substr(OLD.timeline_at, 1, 4);
                DELETE FROM attachment_timeline_stats
                WHERE profile_id=OLD.profile_id AND level='year'
                  AND period_key=substr(OLD.timeline_at, 1, 4) AND total_count <= 0;

                UPDATE attachment_timeline_stats
                SET total_count=total_count-1
                WHERE profile_id=OLD.profile_id AND level='month'
                  AND period_key=substr(OLD.timeline_at, 1, 7)
                  AND OLD.time_precision IN ('month', 'day', 'minute', 'second')
                  AND length(OLD.timeline_at) >= 7;
                DELETE FROM attachment_timeline_stats
                WHERE profile_id=OLD.profile_id AND level='month'
                  AND period_key=substr(OLD.timeline_at, 1, 7) AND total_count <= 0;

                UPDATE attachment_timeline_stats
                SET total_count=total_count-1
                WHERE profile_id=OLD.profile_id AND level='day'
                  AND period_key=substr(OLD.timeline_at, 1, 10)
                  AND OLD.time_precision IN ('day', 'minute', 'second')
                  AND length(OLD.timeline_at) >= 10;
                DELETE FROM attachment_timeline_stats
                WHERE profile_id=OLD.profile_id AND level='day'
                  AND period_key=substr(OLD.timeline_at, 1, 10) AND total_count <= 0;

                UPDATE attachment_timeline_stats
                SET total_count=total_count-1
                WHERE profile_id=OLD.profile_id AND level='hour'
                  AND period_key=substr(OLD.timeline_at, 1, 13)
                  AND OLD.time_precision IN ('minute', 'second')
                  AND length(OLD.timeline_at) >= 13;
                DELETE FROM attachment_timeline_stats
                WHERE profile_id=OLD.profile_id AND level='hour'
                  AND period_key=substr(OLD.timeline_at, 1, 13) AND total_count <= 0;
            END;

            DROP TRIGGER IF EXISTS trg_attachments_timeline_stats_update;
            CREATE TRIGGER trg_attachments_timeline_stats_update
            AFTER UPDATE OF timeline_at, time_precision ON attachments
            BEGIN
                UPDATE attachment_timeline_stats
                SET total_count=total_count-1
                WHERE OLD.timeline_at IS NOT NULL
                  AND OLD.time_precision IS NOT NULL AND OLD.time_precision != 'unknown'
                  AND profile_id=OLD.profile_id AND level='year'
                  AND period_key=substr(OLD.timeline_at, 1, 4);
                DELETE FROM attachment_timeline_stats
                WHERE profile_id=OLD.profile_id AND level='year'
                  AND period_key=substr(OLD.timeline_at, 1, 4) AND total_count <= 0;

                UPDATE attachment_timeline_stats
                SET total_count=total_count-1
                WHERE OLD.timeline_at IS NOT NULL
                  AND OLD.time_precision IN ('month', 'day', 'minute', 'second')
                  AND length(OLD.timeline_at) >= 7
                  AND profile_id=OLD.profile_id AND level='month'
                  AND period_key=substr(OLD.timeline_at, 1, 7);
                DELETE FROM attachment_timeline_stats
                WHERE profile_id=OLD.profile_id AND level='month'
                  AND period_key=substr(OLD.timeline_at, 1, 7) AND total_count <= 0;

                UPDATE attachment_timeline_stats
                SET total_count=total_count-1
                WHERE OLD.timeline_at IS NOT NULL
                  AND OLD.time_precision IN ('day', 'minute', 'second')
                  AND length(OLD.timeline_at) >= 10
                  AND profile_id=OLD.profile_id AND level='day'
                  AND period_key=substr(OLD.timeline_at, 1, 10);
                DELETE FROM attachment_timeline_stats
                WHERE profile_id=OLD.profile_id AND level='day'
                  AND period_key=substr(OLD.timeline_at, 1, 10) AND total_count <= 0;

                UPDATE attachment_timeline_stats
                SET total_count=total_count-1
                WHERE OLD.timeline_at IS NOT NULL
                  AND OLD.time_precision IN ('minute', 'second')
                  AND length(OLD.timeline_at) >= 13
                  AND profile_id=OLD.profile_id AND level='hour'
                  AND period_key=substr(OLD.timeline_at, 1, 13);
                DELETE FROM attachment_timeline_stats
                WHERE profile_id=OLD.profile_id AND level='hour'
                  AND period_key=substr(OLD.timeline_at, 1, 13) AND total_count <= 0;

                INSERT OR IGNORE INTO attachment_timeline_stats(profile_id, level, period_key, total_count)
                SELECT NEW.profile_id, 'year', substr(NEW.timeline_at, 1, 4), 0
                WHERE NEW.timeline_at IS NOT NULL
                  AND NEW.time_precision IS NOT NULL AND NEW.time_precision != 'unknown';
                UPDATE attachment_timeline_stats
                SET total_count=total_count+1
                WHERE NEW.timeline_at IS NOT NULL
                  AND NEW.time_precision IS NOT NULL AND NEW.time_precision != 'unknown'
                  AND profile_id=NEW.profile_id AND level='year'
                  AND period_key=substr(NEW.timeline_at, 1, 4);

                INSERT OR IGNORE INTO attachment_timeline_stats(profile_id, level, period_key, total_count)
                SELECT NEW.profile_id, 'month', substr(NEW.timeline_at, 1, 7), 0
                WHERE NEW.timeline_at IS NOT NULL
                  AND NEW.time_precision IN ('month', 'day', 'minute', 'second')
                  AND length(NEW.timeline_at) >= 7;
                UPDATE attachment_timeline_stats
                SET total_count=total_count+1
                WHERE NEW.timeline_at IS NOT NULL
                  AND NEW.time_precision IN ('month', 'day', 'minute', 'second')
                  AND length(NEW.timeline_at) >= 7
                  AND profile_id=NEW.profile_id AND level='month'
                  AND period_key=substr(NEW.timeline_at, 1, 7);

                INSERT OR IGNORE INTO attachment_timeline_stats(profile_id, level, period_key, total_count)
                SELECT NEW.profile_id, 'day', substr(NEW.timeline_at, 1, 10), 0
                WHERE NEW.timeline_at IS NOT NULL
                  AND NEW.time_precision IN ('day', 'minute', 'second')
                  AND length(NEW.timeline_at) >= 10;
                UPDATE attachment_timeline_stats
                SET total_count=total_count+1
                WHERE NEW.timeline_at IS NOT NULL
                  AND NEW.time_precision IN ('day', 'minute', 'second')
                  AND length(NEW.timeline_at) >= 10
                  AND profile_id=NEW.profile_id AND level='day'
                  AND period_key=substr(NEW.timeline_at, 1, 10);

                INSERT OR IGNORE INTO attachment_timeline_stats(profile_id, level, period_key, total_count)
                SELECT NEW.profile_id, 'hour', substr(NEW.timeline_at, 1, 13), 0
                WHERE NEW.timeline_at IS NOT NULL
                  AND NEW.time_precision IN ('minute', 'second')
                  AND length(NEW.timeline_at) >= 13;
                UPDATE attachment_timeline_stats
                SET total_count=total_count+1
                WHERE NEW.timeline_at IS NOT NULL
                  AND NEW.time_precision IN ('minute', 'second')
                  AND length(NEW.timeline_at) >= 13
                  AND profile_id=NEW.profile_id AND level='hour'
                  AND period_key=substr(NEW.timeline_at, 1, 13);
            END;
            """
        )

    def attachment_timeline_stats_ready(self, *, profile_id: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM attachment_timeline_stats_meta WHERE profile_id=?",
                (profile_id,),
            ).fetchone()
        return row is not None

    def rebuild_attachment_timeline_stats(self, *, profile_id: str) -> dict[str, Any]:
        """Build compact statistics from v9 mirror columns without decrypting metadata."""
        built_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM attachment_timeline_stats WHERE profile_id=?",
                (profile_id,),
            )
            specs = (
                ("year", 4, ("year", "month", "day", "minute", "second")),
                ("month", 7, ("month", "day", "minute", "second")),
                ("day", 10, ("day", "minute", "second")),
                ("hour", 13, ("minute", "second")),
            )
            for level, width, precisions in specs:
                placeholders = ",".join("?" for _ in precisions)
                connection.execute(
                    f"""
                    INSERT INTO attachment_timeline_stats(profile_id, level, period_key, total_count)
                    SELECT profile_id, ?, substr(timeline_at, 1, ?), COUNT(*)
                    FROM attachments
                    WHERE profile_id=?
                      AND timeline_at IS NOT NULL
                      AND time_precision IN ({placeholders})
                      AND length(timeline_at) >= ?
                    GROUP BY profile_id, substr(timeline_at, 1, ?)
                    """,
                    (level, width, profile_id, *precisions, width, width),
                )
            connection.execute(
                """
                INSERT INTO attachment_timeline_stats_meta(profile_id, built_at)
                VALUES(?, ?)
                ON CONFLICT(profile_id) DO UPDATE SET built_at=excluded.built_at
                """,
                (profile_id, built_at),
            )
            period_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM attachment_timeline_stats WHERE profile_id=?",
                    (profile_id,),
                ).fetchone()[0]
            )
            dated_count = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM attachments
                    WHERE profile_id=? AND timeline_at IS NOT NULL
                      AND time_precision IS NOT NULL AND time_precision != 'unknown'
                    """,
                    (profile_id,),
                ).fetchone()[0]
            )
        return {
            "ready": True,
            "built_at": built_at,
            "period_count": period_count,
            "dated_count": dated_count,
        }

    def ensure_attachment_timeline_stats(self, *, profile_id: str) -> dict[str, Any]:
        if self.attachment_timeline_stats_ready(profile_id=profile_id):
            with self.connect() as connection:
                row = connection.execute(
                    "SELECT built_at FROM attachment_timeline_stats_meta WHERE profile_id=?",
                    (profile_id,),
                ).fetchone()
                period_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM attachment_timeline_stats WHERE profile_id=?",
                        (profile_id,),
                    ).fetchone()[0]
                )
            return {
                "ready": True,
                "built_at": str(row["built_at"]) if row else None,
                "period_count": period_count,
                "rebuilt": False,
            }
        result = self.rebuild_attachment_timeline_stats(profile_id=profile_id)
        result["rebuilt"] = True
        return result

    def list_attachment_timeline_stats(
        self,
        *,
        profile_id: str,
        level: str,
        start_key: str,
        end_key: str,
    ) -> list[dict[str, Any]]:
        if level not in {"year", "month", "day", "hour"}:
            raise ValueError("不支持的时间统计粒度")
        self.ensure_attachment_timeline_stats(profile_id=profile_id)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT period_key, total_count
                FROM attachment_timeline_stats
                WHERE profile_id=? AND level=? AND period_key>=? AND period_key<=?
                ORDER BY period_key ASC
                """,
                (profile_id, level, start_key, end_key),
            ).fetchall()
        return [
            {"period_key": str(row["period_key"]), "total_count": int(row["total_count"] or 0)}
            for row in rows
        ]

    def list_attachment_timeline_page(
        self,
        master_key: bytes,
        *,
        profile_id: str,
        start_at: str,
        end_at: str,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Decrypt only one bounded date-range page for the future day timeline."""
        limit = max(1, min(200, int(limit)))
        offset = max(0, int(offset))
        where = """
            profile_id=?
            AND timeline_at>=? AND timeline_at<?
            AND time_precision IN ('day', 'minute', 'second')
        """
        with self.connect() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM attachments WHERE {where}",
                    (profile_id, start_at, end_at),
                ).fetchone()[0]
            )
            rows = connection.execute(
                f"""
                SELECT id, profile_id, kind, content_id, storage_kind, media_id,
                       metadata_nonce, metadata_ciphertext,
                       timeline_at, timeline_end_at, time_precision, time_source,
                       time_confidence, timezone_offset, created_at, updated_at
                FROM attachments
                WHERE {where}
                ORDER BY timeline_at ASC, id ASC
                LIMIT ? OFFSET ?
                """,
                (profile_id, start_at, end_at, limit, offset),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            metadata = decrypt_json(
                master_key,
                row["metadata_nonce"],
                row["metadata_ciphertext"],
                aad=self._aad(ATTACHMENT_META_AAD_PREFIX, row["id"]),
            )
            items.append(
                {
                    "id": row["id"],
                    "profile_id": row["profile_id"],
                    "kind": row["kind"],
                    "content_id": row["content_id"],
                    "storage_kind": row["storage_kind"],
                    "media_id": row["media_id"],
                    "timeline_at": row["timeline_at"],
                    "timeline_end_at": row["timeline_end_at"],
                    "time_precision": row["time_precision"],
                    "time_source": row["time_source"],
                    "time_confidence": row["time_confidence"],
                    "timezone_offset": row["timezone_offset"],
                    **metadata,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        next_offset = offset + len(items)
        return {
            "items": items,
            "total": total,
            "offset": offset,
            "limit": limit,
            "next_offset": next_offset if next_offset < total else None,
            "has_more": next_offset < total,
        }

    @staticmethod
    def _attachment_period_bounds(scope: str, period_key: str) -> tuple[str, str]:
        """Return lexicographic ISO bounds for one indexed attachment period."""
        if scope == "year":
            year = int(period_key[:4])
            return f"{year:04d}", f"{year + 1:04d}"
        if scope == "month":
            year, month = (int(part) for part in period_key[:7].split("-"))
            if month == 12:
                return f"{year:04d}-12", f"{year + 1:04d}-01"
            return f"{year:04d}-{month:02d}", f"{year:04d}-{month + 1:02d}"
        if scope == "day":
            selected = datetime.strptime(period_key[:10], "%Y-%m-%d")
            next_day = selected + timedelta(days=1)
            return selected.strftime("%Y-%m-%d"), next_day.strftime("%Y-%m-%d")
        raise ValueError("不支持的资料时间范围")

    def list_attachment_period_page(
        self,
        master_key: bytes,
        *,
        profile_id: str,
        scope: str,
        period_key: str,
        limit: int = 12,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Decrypt only one indexed period page for the right-side life drawer."""
        limit = max(1, min(100, int(limit)))
        offset = max(0, int(offset))
        start_at, end_at = self._attachment_period_bounds(scope, period_key)
        visible_source = """
            (
                kind IS NULL
                OR (kind='event' AND EXISTS(
                    SELECT 1 FROM events source
                    WHERE source.id=attachments.content_id
                      AND source.profile_id=attachments.profile_id
                      AND source.deleted_at IS NULL
                ))
                OR (kind='memory' AND EXISTS(
                    SELECT 1 FROM memories source
                    WHERE source.id=attachments.content_id
                      AND source.profile_id=attachments.profile_id
                      AND source.deleted_at IS NULL
                ))
                OR (kind='plan' AND EXISTS(
                    SELECT 1 FROM plans source
                    WHERE source.id=attachments.content_id
                      AND source.profile_id=attachments.profile_id
                      AND source.deleted_at IS NULL
                ))
            )
        """
        where = f"""
            profile_id=?
            AND timeline_at IS NOT NULL
            AND timeline_at>=? AND timeline_at<?
            AND {visible_source}
        """
        with self.connect() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM attachments WHERE {where}",
                    (profile_id, start_at, end_at),
                ).fetchone()[0]
            )
            rows = connection.execute(
                f"""
                SELECT id, profile_id, kind, content_id, storage_kind, media_id,
                       metadata_nonce, metadata_ciphertext,
                       timeline_at, timeline_end_at, time_precision, time_source,
                       time_confidence, timezone_offset, created_at, updated_at
                FROM attachments
                WHERE {where}
                ORDER BY timeline_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (profile_id, start_at, end_at, limit, offset),
            ).fetchall()

        items: list[dict[str, Any]] = []
        for row in rows:
            metadata = decrypt_json(
                master_key,
                row["metadata_nonce"],
                row["metadata_ciphertext"],
                aad=self._aad(ATTACHMENT_META_AAD_PREFIX, row["id"]),
            )
            items.append(
                {
                    "id": row["id"],
                    "profile_id": row["profile_id"],
                    "kind": row["kind"],
                    "content_id": row["content_id"],
                    "storage_kind": row["storage_kind"],
                    "media_id": row["media_id"],
                    "timeline_at": row["timeline_at"],
                    "timeline_end_at": row["timeline_end_at"],
                    "time_precision": row["time_precision"],
                    "time_source": row["time_source"],
                    "time_confidence": row["time_confidence"],
                    "timezone_offset": row["timezone_offset"],
                    **metadata,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )

        next_offset = offset + len(items)
        return {
            "items": items,
            "total": total,
            "offset": offset,
            "limit": limit,
            "next_offset": next_offset if next_offset < total else None,
            "has_more": next_offset < total,
        }

    def list_attachment_timeline_minute_counts(
        self,
        *,
        profile_id: str,
        start_at: str,
        end_at: str,
    ) -> list[dict[str, Any]]:
        """Return occupied minute buckets without decrypting attachment metadata."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT substr(timeline_at, 1, 16) AS minute_key, COUNT(*) AS total_count
                FROM attachments
                WHERE profile_id=?
                  AND timeline_at>=? AND timeline_at<?
                  AND time_precision IN ('minute', 'second')
                GROUP BY minute_key
                ORDER BY minute_key ASC
                """,
                (profile_id, start_at, end_at),
            ).fetchall()
        return [
            {"period_key": str(row["minute_key"]), "total_count": int(row["total_count"] or 0)}
            for row in rows
            if row["minute_key"]
        ]

    def attachment_timeline_neighbor_days(
        self,
        *,
        profile_id: str,
        day_key: str,
    ) -> dict[str, str | None]:
        """Return nearest previous/next occupied day from the lightweight stats table."""
        self.ensure_attachment_timeline_stats(profile_id=profile_id)
        with self.connect() as connection:
            previous = connection.execute(
                """
                SELECT period_key
                FROM attachment_timeline_stats
                WHERE profile_id=? AND level='day' AND total_count>0 AND period_key<?
                ORDER BY period_key DESC
                LIMIT 1
                """,
                (profile_id, day_key),
            ).fetchone()
            following = connection.execute(
                """
                SELECT period_key
                FROM attachment_timeline_stats
                WHERE profile_id=? AND level='day' AND total_count>0 AND period_key>?
                ORDER BY period_key ASC
                LIMIT 1
                """,
                (profile_id, day_key),
            ).fetchone()
        return {
            "previous_date": str(previous["period_key"]) if previous else None,
            "next_date": str(following["period_key"]) if following else None,
        }

    def attachment_timeline_backfill_status(self, *, profile_id: str) -> dict[str, int]:
        """Return lightweight counts for the v0.0.10.2 timeline mirror backfill.

        ``time_precision='unknown'`` marks a record that has already been examined
        but still has no reliable date.  Those rows belong to the future
        "时间待确认" bucket and must not be retried on every backfill pass.
        """
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN timeline_at IS NOT NULL THEN 1 ELSE 0 END) AS indexed,
                    SUM(CASE WHEN timeline_at IS NULL AND time_precision='unknown' THEN 1 ELSE 0 END) AS undated,
                    SUM(CASE WHEN timeline_at IS NULL AND time_precision IS NULL THEN 1 ELSE 0 END) AS pending
                FROM attachments
                WHERE profile_id=?
                """,
                (profile_id,),
            ).fetchone()
        return {
            "total": int(row["total"] or 0),
            "indexed": int(row["indexed"] or 0),
            "undated": int(row["undated"] or 0),
            "pending": int(row["pending"] or 0),
        }

    def list_attachment_timeline_backfill_candidates(
        self,
        *,
        profile_id: str,
        limit: int = 32,
        after_created_at: str | None = None,
        after_id: str | None = None,
    ) -> list[dict[str, str]]:
        """Return a bounded page of legacy attachment ids that still need indexing."""
        limit = max(1, min(256, int(limit)))
        params: list[Any] = [profile_id]
        query = """
            SELECT id, created_at
            FROM attachments
            WHERE profile_id=?
              AND timeline_at IS NULL
              AND time_precision IS NULL
        """
        if after_created_at is not None and after_id is not None:
            query += " AND (created_at > ? OR (created_at = ? AND id > ?))"
            params.extend([after_created_at, after_created_at, after_id])
        query += " ORDER BY created_at ASC, id ASC LIMIT ?"
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [{"id": str(row["id"]), "created_at": str(row["created_at"])} for row in rows]

    def sync_attachment_timeline_mirror(
        self,
        *,
        profile_id: str,
        attachment_id: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Mirror already-decrypted legacy metadata into queryable timeline columns.

        This intentionally does not rewrite the encrypted metadata blob or modify
        the attachment's user-visible ``updated_at`` timestamp.
        """
        timeline = self._attachment_timeline_columns(metadata)
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE attachments
                SET timeline_at=?, timeline_end_at=?, time_precision=?, time_source=?,
                    time_confidence=?, timezone_offset=?
                WHERE id=? AND profile_id=?
                """,
                (
                    timeline["timeline_at"],
                    timeline["timeline_end_at"],
                    timeline["time_precision"],
                    timeline["time_source"],
                    timeline["time_confidence"],
                    timeline["timezone_offset"],
                    attachment_id,
                    profile_id,
                ),
            )
            if cursor.rowcount != 1:
                raise DatabaseContentNotFound("附件不存在")
        return timeline

    def mark_attachment_timeline_unknown(
        self,
        *,
        profile_id: str,
        attachment_id: str,
    ) -> None:
        """Mark a successfully inspected record as having no reliable time."""
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE attachments
                SET timeline_at=NULL,
                    timeline_end_at=NULL,
                    time_precision='unknown',
                    time_source=COALESCE(time_source, 'undetermined'),
                    time_confidence='unknown'
                WHERE id=? AND profile_id=?
                """,
                (attachment_id, profile_id),
            )
            if cursor.rowcount != 1:
                raise DatabaseContentNotFound("附件不存在")

    def _ensure_material_scan_schema(self, connection: sqlite3.Connection) -> None:
        """v11: encrypted local scan sources plus a lightweight incremental file index."""
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS material_scan_sources (
                id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL,
                config_nonce BLOB NOT NULL,
                config_ciphertext BLOB NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_scan_started_at TEXT,
                last_scan_completed_at TEXT,
                FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS material_scan_files (
                source_id TEXT NOT NULL,
                path_hash TEXT NOT NULL,
                file_identity TEXT,
                size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
                mtime_ns INTEGER NOT NULL CHECK(mtime_ns >= 0),
                attachment_id TEXT,
                state TEXT NOT NULL CHECK(state IN ('imported','duplicate','missing','failed','ignored')),
                last_seen_scan TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                imported_at TEXT,
                updated_at TEXT NOT NULL,
                error_code TEXT,
                PRIMARY KEY(source_id, path_hash),
                FOREIGN KEY(source_id) REFERENCES material_scan_sources(id) ON DELETE CASCADE,
                FOREIGN KEY(attachment_id) REFERENCES attachments(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_material_scan_sources_profile
            ON material_scan_sources(profile_id, enabled, created_at);

            CREATE INDEX IF NOT EXISTS idx_material_scan_files_identity
            ON material_scan_files(source_id, file_identity)
            WHERE file_identity IS NOT NULL;

            CREATE INDEX IF NOT EXISTS idx_material_scan_files_attachment
            ON material_scan_files(attachment_id)
            WHERE attachment_id IS NOT NULL;
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
                    storage_kind TEXT NOT NULL DEFAULT 'blob-v1'
                        CHECK(storage_kind IN ('blob-v1', 'chunked-v1')),
                    file_nonce BLOB,
                    media_id TEXT,
                    metadata_nonce BLOB NOT NULL,
                    metadata_ciphertext BLOB NOT NULL,
                    timeline_at TEXT,
                    timeline_end_at TEXT,
                    time_precision TEXT CHECK(time_precision IS NULL OR time_precision IN ('year','month','day','minute','second','unknown')),
                    time_source TEXT,
                    time_confidence TEXT CHECK(time_confidence IS NULL OR time_confidence IN ('high','medium','low','unknown')),
                    timezone_offset TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                    CHECK((kind IS NULL AND content_id IS NULL) OR (kind IS NOT NULL AND content_id IS NOT NULL)),
                    CHECK(
                        (storage_kind='blob-v1' AND file_nonce IS NOT NULL AND media_id IS NULL)
                        OR
                        (storage_kind='chunked-v1' AND file_nonce IS NULL AND media_id IS NOT NULL)
                    )
                );

                CREATE INDEX IF NOT EXISTS idx_attachments_content
                ON attachments(profile_id, kind, content_id, created_at);

                CREATE INDEX IF NOT EXISTS idx_attachments_profile
                ON attachments(profile_id, created_at);
                """
            )
            self._ensure_material_attachment_schema(connection)
            self._ensure_attachment_storage_schema(connection)
            self._ensure_attachment_timeline_schema(connection)
            self._ensure_attachment_timeline_stats_schema(connection)
            self._ensure_material_scan_schema(connection)
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

            scan_source_rows = connection.execute(
                "SELECT id, config_nonce, config_ciphertext FROM material_scan_sources"
            ).fetchall() if schema_version >= 11 else []
            for row in scan_source_rows:
                decrypt_json(
                    master_key,
                    row["config_nonce"],
                    row["config_ciphertext"],
                    aad=self._aad(MATERIAL_SCAN_SOURCE_AAD_PREFIX, row["id"]),
                )
            counts["material_scan_source"] = len(scan_source_rows)
            verified_records += len(scan_source_rows)

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
        file_nonce: bytes | None,
        metadata: dict[str, Any],
        timestamp: str,
        storage_kind: str = "blob-v1",
        media_id: str | None = None,
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
        storage_kind = str(storage_kind or "").strip()
        if storage_kind not in {"blob-v1", "chunked-v1"}:
            raise ValueError("不支持的资料存储类型")
        if storage_kind == "blob-v1":
            if file_nonce is None or media_id is not None:
                raise ValueError("普通附件存储参数无效")
        else:
            if file_nonce is not None or not media_id:
                raise ValueError("大型媒体存储参数无效")
        metadata_nonce, metadata_ciphertext = encrypt_json(
            master_key,
            metadata,
            aad=self._aad(ATTACHMENT_META_AAD_PREFIX, attachment_id),
        )
        timeline = self._attachment_timeline_columns(metadata)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO attachments(
                    id, profile_id, kind, content_id, storage_kind, file_nonce, media_id,
                    metadata_nonce, metadata_ciphertext, timeline_at, timeline_end_at,
                    time_precision, time_source, time_confidence, timezone_offset,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attachment_id,
                    profile_id,
                    kind,
                    content_id,
                    storage_kind,
                    file_nonce,
                    media_id,
                    metadata_nonce,
                    metadata_ciphertext,
                    timeline["timeline_at"],
                    timeline["timeline_end_at"],
                    timeline["time_precision"],
                    timeline["time_source"],
                    timeline["time_confidence"],
                    timeline["timezone_offset"],
                    timestamp,
                    timestamp,
                ),
            )
        return {
            "id": attachment_id,
            "profile_id": profile_id,
            "kind": kind,
            "content_id": content_id,
            "storage_kind": storage_kind,
            "file_nonce": file_nonce,
            "media_id": media_id,
            **timeline,
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
        timeline = self._attachment_timeline_columns(metadata)
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE attachments
                SET metadata_nonce=?, metadata_ciphertext=?,
                    timeline_at=?, timeline_end_at=?, time_precision=?, time_source=?,
                    time_confidence=?, timezone_offset=?, updated_at=?
                WHERE id=? AND profile_id=?
                """,
                (
                    metadata_nonce, metadata_ciphertext,
                    timeline["timeline_at"], timeline["timeline_end_at"],
                    timeline["time_precision"], timeline["time_source"],
                    timeline["time_confidence"], timeline["timezone_offset"],
                    timestamp, attachment_id, profile_id,
                ),
            )
            if cursor.rowcount != 1:
                raise DatabaseContentNotFound("附件不存在")
            row = connection.execute(
                """
                SELECT id, profile_id, kind, content_id, storage_kind, file_nonce, media_id,
                       timeline_at, timeline_end_at, time_precision, time_source,
                       time_confidence, timezone_offset, created_at, updated_at
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
            "storage_kind": row["storage_kind"],
            "file_nonce": row["file_nonce"],
            "media_id": row["media_id"],
            "timeline_at": row["timeline_at"],
            "timeline_end_at": row["timeline_end_at"],
            "time_precision": row["time_precision"],
            "time_source": row["time_source"],
            "time_confidence": row["time_confidence"],
            "timezone_offset": row["timezone_offset"],
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
                SELECT id, profile_id, kind, content_id, storage_kind, file_nonce, media_id,
                       metadata_nonce, metadata_ciphertext, timeline_at, timeline_end_at,
                       time_precision, time_source, time_confidence, timezone_offset,
                       created_at, updated_at
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
                    "storage_kind": row["storage_kind"],
                    "file_nonce": row["file_nonce"],
                    "media_id": row["media_id"],
                    "timeline_at": row["timeline_at"],
                    "timeline_end_at": row["timeline_end_at"],
                    "time_precision": row["time_precision"],
                    "time_source": row["time_source"],
                    "time_confidence": row["time_confidence"],
                    "timezone_offset": row["timezone_offset"],
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
                SELECT id, profile_id, kind, content_id, storage_kind, file_nonce, media_id,
                       metadata_nonce, metadata_ciphertext, timeline_at, timeline_end_at,
                       time_precision, time_source, time_confidence, timezone_offset,
                       created_at, updated_at
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
            "storage_kind": row["storage_kind"],
            "file_nonce": row["file_nonce"],
            "media_id": row["media_id"],
            "timeline_at": row["timeline_at"],
            "timeline_end_at": row["timeline_end_at"],
            "time_precision": row["time_precision"],
            "time_source": row["time_source"],
            "time_confidence": row["time_confidence"],
            "timezone_offset": row["timezone_offset"],
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
                SELECT id, storage_kind, media_id FROM attachments
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
        return {
            "id": attachment_id,
            "deleted": True,
            "storage_kind": row["storage_kind"],
            "media_id": row["media_id"],
        }

    def delete_independent_material(
        self,
        *,
        profile_id: str,
        attachment_id: str,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id, kind, content_id, storage_kind, media_id FROM attachments
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
        return {
            "id": attachment_id,
            "deleted": True,
            "storage_kind": row["storage_kind"],
            "media_id": row["media_id"],
        }

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
            SELECT id, profile_id, kind, content_id, storage_kind, file_nonce, media_id,
                   metadata_nonce, metadata_ciphertext, timeline_at, timeline_end_at,
                   time_precision, time_source, time_confidence, timezone_offset,
                   created_at, updated_at
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
                        "storage_kind": row["storage_kind"],
                        "file_nonce": row["file_nonce"],
                        "media_id": row["media_id"],
                        "timeline_at": row["timeline_at"],
                        "timeline_end_at": row["timeline_end_at"],
                        "time_precision": row["time_precision"],
                        "time_source": row["time_source"],
                        "time_confidence": row["time_confidence"],
                        "timezone_offset": row["timezone_offset"],
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

    def create_material_scan_source(
        self,
        master_key: bytes,
        *,
        source_id: str,
        profile_id: str,
        config: dict[str, Any],
        timestamp: str,
    ) -> dict[str, Any]:
        nonce, ciphertext = encrypt_json(
            master_key,
            config,
            aad=self._aad(MATERIAL_SCAN_SOURCE_AAD_PREFIX, source_id),
        )
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO material_scan_sources(
                    id, profile_id, config_nonce, config_ciphertext, enabled,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (source_id, profile_id, nonce, ciphertext, timestamp, timestamp),
            )
        return {
            "id": source_id, "profile_id": profile_id, **config,
            "enabled": True, "created_at": timestamp, "updated_at": timestamp,
            "last_scan_started_at": None, "last_scan_completed_at": None,
            "file_counts": {},
        }

    def list_material_scan_sources(
        self, master_key: bytes, *, profile_id: str
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, profile_id, config_nonce, config_ciphertext, enabled,
                       created_at, updated_at, last_scan_started_at, last_scan_completed_at
                FROM material_scan_sources
                WHERE profile_id=?
                ORDER BY created_at ASC, id ASC
                """,
                (profile_id,),
            ).fetchall()
            count_rows = connection.execute(
                """
                SELECT f.source_id, f.state, COUNT(*) AS count
                FROM material_scan_files f
                JOIN material_scan_sources s ON s.id=f.source_id
                WHERE s.profile_id=?
                GROUP BY f.source_id, f.state
                """,
                (profile_id,),
            ).fetchall()
        counts: dict[str, dict[str, int]] = {}
        for row in count_rows:
            counts.setdefault(row["source_id"], {})[row["state"]] = int(row["count"])
        values: list[dict[str, Any]] = []
        for row in rows:
            config = decrypt_json(
                master_key,
                row["config_nonce"],
                row["config_ciphertext"],
                aad=self._aad(MATERIAL_SCAN_SOURCE_AAD_PREFIX, row["id"]),
            )
            values.append(
                {
                    "id": row["id"],
                    "profile_id": row["profile_id"],
                    **config,
                    "enabled": bool(row["enabled"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "last_scan_started_at": row["last_scan_started_at"],
                    "last_scan_completed_at": row["last_scan_completed_at"],
                    "file_counts": counts.get(row["id"], {}),
                }
            )
        return values

    def get_material_scan_source(
        self, master_key: bytes, *, profile_id: str, source_id: str
    ) -> dict[str, Any]:
        values = self.list_material_scan_sources(master_key, profile_id=profile_id)
        for value in values:
            if value["id"] == source_id:
                return value
        raise DatabaseContentNotFound("扫描源不存在")

    def set_material_scan_source_enabled(
        self, *, profile_id: str, source_id: str, enabled: bool, timestamp: str
    ) -> None:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE material_scan_sources SET enabled=?, updated_at=?
                WHERE id=? AND profile_id=?
                """,
                (1 if enabled else 0, timestamp, source_id, profile_id),
            )
            if cursor.rowcount != 1:
                raise DatabaseContentNotFound("扫描源不存在")

    def delete_material_scan_source(self, *, profile_id: str, source_id: str) -> None:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM material_scan_sources WHERE id=? AND profile_id=?",
                (source_id, profile_id),
            )
            if cursor.rowcount != 1:
                raise DatabaseContentNotFound("扫描源不存在")

    def mark_material_scan_source_started(
        self, *, profile_id: str, source_id: str, timestamp: str
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE material_scan_sources
                SET last_scan_started_at=?, updated_at=?
                WHERE id=? AND profile_id=?
                """,
                (timestamp, timestamp, source_id, profile_id),
            )

    def mark_material_scan_source_completed(
        self, *, profile_id: str, source_id: str, timestamp: str
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE material_scan_sources
                SET last_scan_completed_at=?, updated_at=?
                WHERE id=? AND profile_id=?
                """,
                (timestamp, timestamp, source_id, profile_id),
            )

    def get_material_scan_file(
        self, *, source_id: str, path_hash: str
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT source_id, path_hash, file_identity, size_bytes, mtime_ns,
                       attachment_id, state, last_seen_scan, last_seen_at, imported_at,
                       updated_at, error_code
                FROM material_scan_files
                WHERE source_id=? AND path_hash=?
                """,
                (source_id, path_hash),
            ).fetchone()
        return dict(row) if row is not None else None

    def find_material_scan_file_by_identity(
        self, *, source_id: str, file_identity: str
    ) -> dict[str, Any] | None:
        if not file_identity:
            return None
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT source_id, path_hash, file_identity, size_bytes, mtime_ns,
                       attachment_id, state, last_seen_scan, last_seen_at, imported_at,
                       updated_at, error_code
                FROM material_scan_files
                WHERE source_id=? AND file_identity=?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (source_id, file_identity),
            ).fetchone()
        return dict(row) if row is not None else None

    def upsert_material_scan_file(
        self,
        *,
        source_id: str,
        path_hash: str,
        file_identity: str | None,
        size_bytes: int,
        mtime_ns: int,
        attachment_id: str | None,
        state: str,
        scan_token: str,
        timestamp: str,
        imported_at: str | None = None,
        error_code: str | None = None,
        previous_path_hash: str | None = None,
    ) -> None:
        allowed = {"imported", "duplicate", "missing", "failed", "ignored"}
        if state not in allowed:
            raise ValueError("扫描文件状态无效")
        with self.connect() as connection:
            if previous_path_hash and previous_path_hash != path_hash:
                connection.execute(
                    "DELETE FROM material_scan_files WHERE source_id=? AND path_hash=?",
                    (source_id, previous_path_hash),
                )
            connection.execute(
                """
                INSERT INTO material_scan_files(
                    source_id, path_hash, file_identity, size_bytes, mtime_ns,
                    attachment_id, state, last_seen_scan, last_seen_at, imported_at,
                    updated_at, error_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, path_hash) DO UPDATE SET
                    file_identity=excluded.file_identity,
                    size_bytes=excluded.size_bytes,
                    mtime_ns=excluded.mtime_ns,
                    attachment_id=excluded.attachment_id,
                    state=excluded.state,
                    last_seen_scan=excluded.last_seen_scan,
                    last_seen_at=excluded.last_seen_at,
                    imported_at=COALESCE(excluded.imported_at, material_scan_files.imported_at),
                    updated_at=excluded.updated_at,
                    error_code=excluded.error_code
                """,
                (
                    source_id, path_hash, file_identity, int(size_bytes), int(mtime_ns),
                    attachment_id, state, scan_token, timestamp, imported_at, timestamp, error_code,
                ),
            )

    def mark_unseen_material_scan_files_missing(
        self, *, source_id: str, scan_token: str, timestamp: str
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE material_scan_files
                SET state='missing', updated_at=?, error_code=NULL
                WHERE source_id=? AND last_seen_scan<>? AND state<>'missing'
                """,
                (timestamp, source_id, scan_token),
            )
            return max(0, int(cursor.rowcount or 0))

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

        # Material presence is already mirrored into the lightweight timeline
        # statistics table.  Use it directly here instead of decrypting every
        # attachment metadata row on each home-page load.
        material_ranges = (
            ("dates", "day", start_date, end_date),
            ("months", "month", start_date[:7], end_date[:7]),
            ("years", "year", start_date[:4], end_date[:4]),
        )
        for map_name, level, start_key, end_key in material_ranges:
            for item in self.list_attachment_timeline_stats(
                profile_id=profile_id,
                level=level,
                start_key=start_key,
                end_key=end_key,
            ):
                if int(item.get("total_count") or 0) <= 0:
                    continue
                state = result[map_name].setdefault(item["period_key"], self._empty_state())
                state["has_material"] = True
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

