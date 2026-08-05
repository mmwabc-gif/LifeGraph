from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.security.crypto import decrypt_json, encrypt_json


PROFILE_AAD = b"lifegraph:v1:profile"


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def initialize_schema(self) -> None:
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
                """
            )
            connection.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', '1')"
            )

    def save_profile(self, master_key: bytes, profile_id: str, payload: dict[str, Any], timestamp: str) -> None:
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
