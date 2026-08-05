from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8765
    data_dir: Path = PROJECT_ROOT / "data"
    session_ttl_seconds: int = 1800

    @classmethod
    def from_env(cls) -> "Settings":
        raw_data_dir = os.getenv("LIFEGRAPH_DATA_DIR", str(PROJECT_ROOT / "data"))
        data_dir = Path(raw_data_dir)
        if not data_dir.is_absolute():
            data_dir = (PROJECT_ROOT / data_dir).resolve()
        return cls(
            host=os.getenv("LIFEGRAPH_HOST", "127.0.0.1"),
            port=int(os.getenv("LIFEGRAPH_PORT", "8765")),
            data_dir=data_dir,
            session_ttl_seconds=int(os.getenv("LIFEGRAPH_SESSION_TTL_SECONDS", "1800")),
        )
