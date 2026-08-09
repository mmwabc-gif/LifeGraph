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
        assert {"schema_meta", "profiles", "events", "memories", "plans", "attachments"}.issubset(tables)
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


def test_schema_v6_attachments_are_upgraded_for_independent_materials(tmp_path: Path) -> None:
    database_path = tmp_path / "lifegraph.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO schema_meta(key, value) VALUES('schema_version', '6');
            CREATE TABLE profiles (
                id TEXT PRIMARY KEY, nonce BLOB NOT NULL, ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1
            );
            INSERT INTO profiles VALUES('profile-1', X'00', X'01', '2026-08-08', '2026-08-08', 1);
            CREATE TABLE attachments (
                id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('event', 'memory', 'plan')),
                content_id TEXT NOT NULL,
                file_nonce BLOB NOT NULL,
                metadata_nonce BLOB NOT NULL,
                metadata_ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO attachments VALUES(
                'attachment-1', 'profile-1', 'memory', 'memory-1', X'01', X'02', X'03',
                '2026-08-08', '2026-08-08'
            );
            """
        )

    database = Database(database_path)
    database.initialize_schema()

    assert database.schema_version() == LATEST_SCHEMA_VERSION
    with database.connect() as connection:
        columns = {row["name"]: row for row in connection.execute("PRAGMA table_info(attachments)")}
        old_row = connection.execute(
            "SELECT kind, content_id FROM attachments WHERE id='attachment-1'"
        ).fetchone()
        connection.execute(
            """
            INSERT INTO attachments(
                id, profile_id, kind, content_id, file_nonce, metadata_nonce,
                metadata_ciphertext, created_at, updated_at
            ) VALUES('material-1', 'profile-1', NULL, NULL, X'01', X'02', X'03', '2026-08-08', '2026-08-08')
            """
        )
    assert columns["kind"]["notnull"] == 0
    assert columns["content_id"]["notnull"] == 0
    assert tuple(old_row) == ("memory", "memory-1")


def test_schema_v7_attachments_are_upgraded_for_chunked_media(tmp_path: Path) -> None:
    database_path = tmp_path / "lifegraph.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO schema_meta(key, value) VALUES('schema_version', '7');
            CREATE TABLE profiles (
                id TEXT PRIMARY KEY, nonce BLOB NOT NULL, ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1
            );
            INSERT INTO profiles VALUES('profile-1', X'00', X'01', '2026-08-09', '2026-08-09', 1);
            CREATE TABLE attachments (
                id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL,
                kind TEXT CHECK(kind IS NULL OR kind IN ('event', 'memory', 'plan')),
                content_id TEXT,
                file_nonce BLOB NOT NULL,
                metadata_nonce BLOB NOT NULL,
                metadata_ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CHECK((kind IS NULL AND content_id IS NULL) OR (kind IS NOT NULL AND content_id IS NOT NULL))
            );
            INSERT INTO attachments VALUES(
                'material-legacy', 'profile-1', NULL, NULL, X'01', X'02', X'03',
                '2026-08-09', '2026-08-09'
            );
            """
        )

    database = Database(database_path)
    database.initialize_schema()

    assert database.schema_version() == LATEST_SCHEMA_VERSION
    with database.connect() as connection:
        columns = {row["name"]: row for row in connection.execute("PRAGMA table_info(attachments)")}
        legacy = connection.execute(
            "SELECT storage_kind, file_nonce, media_id FROM attachments WHERE id='material-legacy'"
        ).fetchone()
        connection.execute(
            """
            INSERT INTO attachments(
                id, profile_id, kind, content_id, storage_kind, file_nonce, media_id,
                metadata_nonce, metadata_ciphertext, created_at, updated_at
            ) VALUES(
                'material-large', 'profile-1', NULL, NULL, 'chunked-v1', NULL, 'media-1',
                X'02', X'03', '2026-08-09', '2026-08-09'
            )
            """
        )
        large = connection.execute(
            "SELECT storage_kind, file_nonce, media_id FROM attachments WHERE id='material-large'"
        ).fetchone()

    assert {"storage_kind", "media_id"}.issubset(columns)
    assert columns["file_nonce"]["notnull"] == 0
    assert tuple(legacy) == ("blob-v1", b"\x01", None)
    assert tuple(large) == ("chunked-v1", None, "media-1")



def test_schema_v8_attachments_gain_queryable_timeline_columns_without_backfill(tmp_path: Path) -> None:
    database_path = tmp_path / "lifegraph.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO schema_meta(key, value) VALUES('schema_version', '8');
            CREATE TABLE profiles (
                id TEXT PRIMARY KEY, nonce BLOB NOT NULL, ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1
            );
            INSERT INTO profiles VALUES('profile-1', X'00', X'01', '2026-08-09', '2026-08-09', 1);
            CREATE TABLE attachments (
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
            );
            INSERT INTO attachments VALUES(
                'material-v8', 'profile-1', NULL, NULL, 'blob-v1', X'01', NULL,
                X'02', X'03', '2026-08-09', '2026-08-09'
            );
            """
        )

    database = Database(database_path)
    database.initialize_schema()

    assert database.schema_version() == LATEST_SCHEMA_VERSION
    with database.connect() as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(attachments)")}
        row = connection.execute(
            """
            SELECT timeline_at, timeline_end_at, time_precision, time_source,
                   time_confidence, timezone_offset
            FROM attachments WHERE id='material-v8'
            """
        ).fetchone()
        indexes = {
            item["name"]
            for item in connection.execute("PRAGMA index_list(attachments)").fetchall()
        }

    assert {
        "timeline_at", "timeline_end_at", "time_precision", "time_source",
        "time_confidence", "timezone_offset",
    }.issubset(columns)
    # v0.0.10.1 must not decrypt/backfill v8 metadata during startup migration.
    assert tuple(row) == (None, None, None, None, None, None)
    assert "idx_attachments_profile_timeline" in indexes


def test_attachment_writes_keep_queryable_timeline_mirror_in_sync(tmp_path: Path) -> None:
    database = Database(tmp_path / "lifegraph.db")
    database.initialize_schema()
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO profiles(id, nonce, ciphertext, created_at, updated_at, revision)
            VALUES('profile-1', X'00', X'01', '2026-08-09', '2026-08-09', 1)
            """
        )

    master_key = b"k" * 32
    created = database.create_attachment(
        master_key,
        attachment_id="material-1",
        profile_id="profile-1",
        kind=None,
        content_id=None,
        file_nonce=b"nonce",
        metadata={
            "filename": "clip.mp4",
            "timeline_at": "2026-08-09T14:32:18+08:00",
            "timeline_time_source": "exif:DateTimeOriginal",
            "duration_seconds": 60,
        },
        timestamp="2026-08-09T13:00:00+00:00",
    )
    assert created["time_precision"] == "second"
    assert created["time_source"] == "exif:DateTimeOriginal"
    assert created["time_confidence"] == "high"
    assert created["timezone_offset"] == "+08:00"
    assert created["timeline_end_at"] == "2026-08-09T14:33:18+08:00"

    with database.connect() as connection:
        row = connection.execute(
            """
            SELECT timeline_at, timeline_end_at, time_precision, time_source,
                   time_confidence, timezone_offset
            FROM attachments WHERE id='material-1'
            """
        ).fetchone()
    assert tuple(row) == (
        "2026-08-09T14:32:18+08:00",
        "2026-08-09T14:33:18+08:00",
        "second",
        "exif:DateTimeOriginal",
        "high",
        "+08:00",
    )

    updated = database.update_attachment_metadata(
        master_key,
        profile_id="profile-1",
        attachment_id="material-1",
        metadata={
            "filename": "clip.mp4",
            "timeline_at": "2026-08-10T00:00:00+08:00",
            "timeline_time_source": "content:date",
        },
        timestamp="2026-08-09T13:05:00+00:00",
    )
    assert updated["time_precision"] == "day"
    assert updated["time_source"] == "content:date"
    assert updated["time_confidence"] == "medium"
    assert updated["timeline_end_at"] is None



def test_schema_v9_adds_timeline_stats_without_eager_aggregation(tmp_path: Path) -> None:
    database_path = tmp_path / "lifegraph.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO schema_meta(key, value) VALUES('schema_version', '9');
            CREATE TABLE profiles (
                id TEXT PRIMARY KEY, nonce BLOB NOT NULL, ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1
            );
            INSERT INTO profiles VALUES('profile-1', X'00', X'01', '2026-08-09', '2026-08-09', 1);
            CREATE TABLE attachments (
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
                time_precision TEXT,
                time_source TEXT,
                time_confidence TEXT,
                timezone_offset TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CHECK((kind IS NULL AND content_id IS NULL) OR (kind IS NOT NULL AND content_id IS NOT NULL)),
                CHECK(
                    (storage_kind='blob-v1' AND file_nonce IS NOT NULL AND media_id IS NULL)
                    OR
                    (storage_kind='chunked-v1' AND file_nonce IS NULL AND media_id IS NOT NULL)
                )
            );
            INSERT INTO attachments VALUES(
                'material-v9', 'profile-1', NULL, NULL, 'blob-v1', X'01', NULL,
                X'02', X'03', '2020-05-01T08:15:20+08:00', NULL,
                'second', 'file:last_modified', 'medium', '+08:00',
                '2026-08-09', '2026-08-09'
            );
            """
        )

    database = Database(database_path)
    database.initialize_schema()

    assert database.schema_version() == LATEST_SCHEMA_VERSION
    with database.connect() as connection:
        tables = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        triggers = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        stats_count = connection.execute("SELECT COUNT(*) FROM attachment_timeline_stats").fetchone()[0]
        meta_count = connection.execute("SELECT COUNT(*) FROM attachment_timeline_stats_meta").fetchone()[0]

    assert {"attachment_timeline_stats", "attachment_timeline_stats_meta"}.issubset(tables)
    assert {
        "trg_attachments_timeline_stats_insert",
        "trg_attachments_timeline_stats_delete",
        "trg_attachments_timeline_stats_update",
    }.issubset(triggers)
    # v0.0.10.3 keeps startup cheap: existing v9 rows are aggregated lazily on
    # the first timeline-summary request, with no metadata decryption.
    assert stats_count == 0
    assert meta_count == 0

    built = database.ensure_attachment_timeline_stats(profile_id="profile-1")
    assert built["rebuilt"] is True
    with database.connect() as connection:
        assert connection.execute(
            "SELECT total_count FROM attachment_timeline_stats WHERE profile_id='profile-1' AND level='year' AND period_key='2020'"
        ).fetchone()[0] == 1


def test_schema_v10_adds_encrypted_material_scan_tables_without_scanning(tmp_path: Path) -> None:
    database_path = tmp_path / "lifegraph.db"
    database = Database(database_path)
    database.initialize_schema()
    master_key = bytes(range(32))
    database.save_profile(
        master_key,
        "profile-1",
        {
            "display_name": "扫描迁移测试",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
        },
        "2026-08-10T00:00:00+00:00",
    )
    # Simulate the schema marker of a v10 database while leaving all v10 tables intact.
    with database.connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', '10')"
        )
        connection.execute("DROP TABLE IF EXISTS material_scan_files")
        connection.execute("DROP TABLE IF EXISTS material_scan_sources")

    database.initialize_schema()
    assert database.schema_version() == LATEST_SCHEMA_VERSION
    with database.connect() as connection:
        tables = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        source_count = connection.execute("SELECT COUNT(*) FROM material_scan_sources").fetchone()[0]
        file_count = connection.execute("SELECT COUNT(*) FROM material_scan_files").fetchone()[0]
    assert {"material_scan_sources", "material_scan_files"}.issubset(tables)
    # v11 only adds empty scan configuration/index tables during startup. It does
    # not enumerate the filesystem or create any attachment rows during migration.
    assert source_count == 0
    assert file_count == 0
