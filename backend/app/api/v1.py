from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.models import InitializeRequest, UnlockRequest
from app.security.vault import VaultError, VaultManager
from app.services.progress import calculate_progress


router = APIRouter(prefix="/api/v1")


def get_vault(request: Request) -> VaultManager:
    return request.app.state.vault


def envelope(data: object) -> dict:
    return {"ok": True, "data": data}


def require_session(
    vault: Annotated[VaultManager, Depends(get_vault)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_REQUIRED", "message": "需要有效会话"},
        )
    token = authorization.removeprefix("Bearer ").strip()
    if not vault.sessions.validate(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "SESSION_EXPIRED", "message": "会话已失效，请重新解锁"},
        )


@router.get("/system/status")
def system_status(vault: Annotated[VaultManager, Depends(get_vault)]) -> dict:
    return envelope(
        {
            "version": "0.0.1",
            "initialized": vault.is_initialized,
            "unlocked": vault.is_unlocked,
            "api_version": "v1",
            "storage_mode": "sqlite+aead-field-encryption",
        }
    )


@router.post("/auth/initialize")
def initialize(
    payload: InitializeRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        session, generated_recovery = vault.initialize(
            display_name=payload.display_name,
            birth_date=payload.birth_date.isoformat(),
            target_age=payload.target_age,
            timezone=payload.timezone,
            pin=payload.pin,
            recovery_secret=payload.recovery_secret,
        )
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INITIALIZE_FAILED", "message": str(exc)},
        ) from exc
    return envelope(
        {
            "token": session.token,
            "expires_at": session.expires_at,
            "generated_recovery_secret": generated_recovery,
        }
    )


@router.post("/auth/unlock")
def unlock(
    payload: UnlockRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        session = vault.unlock(payload.method, payload.secret)
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIAL", "message": str(exc)},
        ) from exc
    return envelope({"token": session.token, "expires_at": session.expires_at})


@router.post("/auth/lock")
def lock(vault: Annotated[VaultManager, Depends(get_vault)]) -> dict:
    vault.lock()
    return envelope({"locked": True})


@router.get("/profile", dependencies=[Depends(require_session)])
def profile(vault: Annotated[VaultManager, Depends(get_vault)]) -> dict:
    try:
        return envelope(vault.get_profile())
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={"code": "VAULT_LOCKED", "message": str(exc)},
        ) from exc


@router.get("/progress/life", dependencies=[Depends(require_session)])
def progress(vault: Annotated[VaultManager, Depends(get_vault)]) -> dict:
    try:
        return envelope(calculate_progress(vault.get_profile()))
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={"code": "VAULT_LOCKED", "message": str(exc)},
        ) from exc
