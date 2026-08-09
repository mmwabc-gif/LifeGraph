from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass


@dataclass(slots=True)
class Session:
    token: str
    expires_at: float


@dataclass(slots=True)
class MediaTicket:
    token: str
    attachment_id: str
    expires_at: float


class SessionManager:
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl_seconds = ttl_seconds
        # Native <video> requests cannot attach the bearer header. Playback uses
        # an opaque attachment-scoped ticket with a longer sliding TTL so a long
        # film can remain paused without expiring. Locking the vault revokes it.
        self._media_ticket_ttl_seconds = max(int(ttl_seconds), 4 * 60 * 60)
        self._sessions: dict[str, Session] = {}
        self._media_tickets: dict[str, MediaTicket] = {}
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

    def create_media_ticket(self, attachment_id: str) -> MediaTicket:
        now = time.time()
        ticket = MediaTicket(
            token=secrets.token_urlsafe(32),
            attachment_id=str(attachment_id),
            expires_at=now + self._media_ticket_ttl_seconds,
        )
        with self._lock:
            self._media_tickets[ticket.token] = ticket
        return ticket

    def validate_media_ticket(self, token: str, attachment_id: str) -> bool:
        now = time.time()
        with self._lock:
            ticket = self._media_tickets.get(token)
            if ticket is None:
                return False
            if ticket.expires_at <= now or ticket.attachment_id != str(attachment_id):
                self._media_tickets.pop(token, None)
                return False
            ticket.expires_at = now + self._media_ticket_ttl_seconds
            return True

    def revoke_all(self) -> None:
        with self._lock:
            self._sessions.clear()
            self._media_tickets.clear()
