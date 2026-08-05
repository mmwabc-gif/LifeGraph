from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass


@dataclass(slots=True)
class Session:
    token: str
    expires_at: float


class SessionManager:
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl_seconds = ttl_seconds
        self._sessions: dict[str, Session] = {}
        self._lock = threading.RLock()

    def create(self) -> Session:
        now = time.time()
        session = Session(
            token=secrets.token_urlsafe(32),
            expires_at=now + self._ttl_seconds,
        )
        with self._lock:
            self._sessions[session.token] = session
        return session

    def validate(self, token: str) -> bool:
        now = time.time()
        with self._lock:
            session = self._sessions.get(token)
            if session is None:
                return False
            if session.expires_at <= now:
                self._sessions.pop(token, None)
                return False
            session.expires_at = now + self._ttl_seconds
            return True

    def revoke_all(self) -> None:
        with self._lock:
            self._sessions.clear()
