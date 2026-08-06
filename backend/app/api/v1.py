from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from app.models import EventCreateRequest, InitializeRequest, MemoryCreateRequest, PlanCreateRequest, UnlockRequest
from app.security.vault import VaultError, VaultManager
from app.services.date_detail import DateOutOfLifeRange
from app.services.periods import child_periods, resolve_period
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


def locked_error(exc: VaultError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_423_LOCKED,
        detail={"code": "VAULT_LOCKED", "message": str(exc)},
    )


def date_range_error(exc: DateOutOfLifeRange) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "DATE_OUT_OF_RANGE", "message": str(exc)},
    )


def invalid_period_error(exc: ValueError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "INVALID_PERIOD", "message": str(exc)},
    )


def period_content(vault: VaultManager, scope: str, period_key: str) -> dict:
    profile_value = vault.get_profile()
    description = resolve_period(profile_value, scope, period_key)
    events = vault.list_events_for_period(scope, period_key)
    memories = vault.list_memories_for_period(scope, period_key)
    plans = vault.list_plans_for_period(scope, period_key)
    description.update(
        {
            "content_state": {
                "has_event": bool(events),
                "has_memory": bool(memories),
                "has_plan": bool(plans),
            },
            "events": events,
            "memories": memories,
            "plans": plans,
            "children": child_periods(profile_value, description),
        }
    )
    return description


@router.get("/system/status")
def system_status(vault: Annotated[VaultManager, Depends(get_vault)]) -> dict:
    return envelope(
        {
            "version": "0.0.2",
            "initialized": vault.is_initialized,
            "unlocked": vault.is_unlocked,
            "api_version": "v1",
            "schema_version": vault.database.schema_version(),
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
        raise locked_error(exc) from exc


@router.get("/progress/life", dependencies=[Depends(require_session)])
def progress(vault: Annotated[VaultManager, Depends(get_vault)]) -> dict:
    try:
        return envelope(calculate_progress(vault.get_profile()))
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.get("/dates/content-status", dependencies=[Depends(require_session)])
def content_status(
    vault: Annotated[VaultManager, Depends(get_vault)],
    start: Annotated[date, Query()],
    end: Annotated[date, Query()],
) -> dict:
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_DATE_RANGE", "message": "开始日期不能晚于结束日期"},
        )
    if (end - start).days > 55_000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "DATE_RANGE_TOO_LARGE", "message": "日期范围过大"},
        )
    try:
        statuses = vault.get_content_status(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )
        return envelope(statuses)
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.get("/periods/{scope}/{period_key}", dependencies=[Depends(require_session)])
def period_detail(
    scope: Literal["year", "month", "day"],
    period_key: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(period_content(vault, scope, period_key))
    except DateOutOfLifeRange as exc:
        raise date_range_error(exc) from exc
    except ValueError as exc:
        raise invalid_period_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.get("/dates/{selected_date}", dependencies=[Depends(require_session)])
def date_detail(
    selected_date: date,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(period_content(vault, "day", selected_date.isoformat()))
    except DateOutOfLifeRange as exc:
        raise date_range_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


def resolve_payload_target(vault: VaultManager, scope: str, period_key: str) -> dict:
    profile_value = vault.get_profile()
    return resolve_period(profile_value, scope, period_key)


@router.post("/events", dependencies=[Depends(require_session)])
def create_event(
    payload: EventCreateRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        description = resolve_payload_target(vault, payload.time_scope, payload.period_key or "")
        event = vault.create_event(
            event_date=description["anchor_date"],
            time_scope=payload.time_scope,
            period_key=payload.period_key,
            title=payload.title,
            content=payload.content,
        )
        return envelope(event)
    except DateOutOfLifeRange as exc:
        raise date_range_error(exc) from exc
    except ValueError as exc:
        raise invalid_period_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.post("/memories", dependencies=[Depends(require_session)])
def create_memory(
    payload: MemoryCreateRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        description = resolve_payload_target(vault, payload.time_scope, payload.period_key or "")
        memory = vault.create_memory(
            memory_date=description["anchor_date"],
            time_scope=payload.time_scope,
            period_key=payload.period_key,
            title=payload.title,
            content=payload.content,
        )
        return envelope(memory)
    except DateOutOfLifeRange as exc:
        raise date_range_error(exc) from exc
    except ValueError as exc:
        raise invalid_period_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.post("/plans", dependencies=[Depends(require_session)])
def create_plan(
    payload: PlanCreateRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        description = resolve_payload_target(vault, payload.time_scope, payload.period_key or "")
        if not description["plan_allowed"]:
            code = "PLAN_DATE_IN_PAST" if payload.time_scope == "day" else "PLAN_PERIOD_IN_PAST"
            message = "未来计划不能安排在已经过去的日期" if payload.time_scope == "day" else "未来计划不能安排在已经结束的时间范围"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": code, "message": message},
            )
        plan = vault.create_plan(
            plan_date=description["anchor_date"],
            time_scope=payload.time_scope,
            period_key=payload.period_key,
            title=payload.title,
            content=payload.content,
        )
        return envelope(plan)
    except DateOutOfLifeRange as exc:
        raise date_range_error(exc) from exc
    except ValueError as exc:
        raise invalid_period_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc
