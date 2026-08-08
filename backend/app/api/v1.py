from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.models import (
    AutoBackupHistoryClearRequest,
    AutoBackupPolicyUpdateRequest,
    ContentDeleteRequest,
    ContentBulkTagRequest,
    ContentTagSelectionRequest,
    ContentUpdateRequest,
    EventCreateRequest,
    InitializeRequest,
    MemoryCreateRequest,
    PinChangeRequest,
    PinResetRequest,
    PlanCreateRequest,
    ProfileImpactRequest,
    ProfileUpdateRequest,
    RecoveryCredentialChangeRequest,
    TrashClearRequest,
    UnlockRequest,
    TagCreateRequest,
    TagUpdateRequest,
)
from app.security.vault import (
    ContentNotFound,
    ContentRevisionConflict,
    CredentialError,
    TagConflict,
    VaultError,
    VaultManager,
)
from app.services.backup import LIFEVAULT_MEDIA_TYPE, MAX_LIFEVAULT_BYTES
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


def content_not_found_error(exc: ContentNotFound) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "CONTENT_NOT_FOUND", "message": str(exc)},
    )


def revision_conflict_error(exc: ContentRevisionConflict) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "REVISION_CONFLICT", "message": str(exc)},
    )


def tag_conflict_error(exc: TagConflict) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "TAG_NAME_CONFLICT", "message": str(exc)},
    )


def credential_error(exc: CredentialError, code: str = "INVALID_CREDENTIAL") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": code, "message": str(exc)},
    )


def period_content(vault: VaultManager, scope: str, period_key: str) -> dict:
    profile_value = vault.get_profile()
    description = resolve_period(profile_value, scope, period_key)
    events = vault.list_events_for_period(scope, period_key)
    memories = vault.list_memories_for_period(scope, period_key)
    plans = vault.list_plans_for_period(scope, period_key)
    for kind, items in (("event", events), ("memory", memories), ("plan", plans)):
        tags_by_content = vault.list_content_tags_for_items(
            kind=kind, content_ids=[item["id"] for item in items]
        )
        for item in items:
            item["tags"] = tags_by_content.get(item["id"], [])
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
            "version": vault.app_version,
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


@router.post("/auth/reset-pin")
def reset_pin(
    payload: PinResetRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        vault.reset_pin_with_recovery(
            recovery_secret=payload.recovery_secret,
            new_pin=payload.new_pin,
        )
        return envelope({"reset": True, "locked": True})
    except CredentialError as exc:
        raise credential_error(exc, "INVALID_RECOVERY_CREDENTIAL") from exc
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PIN_RESET_FAILED", "message": str(exc)},
        ) from exc


@router.post("/auth/change-pin", dependencies=[Depends(require_session)])
def change_pin(
    payload: PinChangeRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        vault.change_pin(current_pin=payload.current_pin, new_pin=payload.new_pin)
        return envelope({"changed": True, "locked": True})
    except CredentialError as exc:
        raise credential_error(exc, "INVALID_CURRENT_PIN") from exc
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PIN_CHANGE_FAILED", "message": str(exc)},
        ) from exc


@router.get("/security/summary", dependencies=[Depends(require_session)])
def security_summary(
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.get_security_summary())
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.post("/auth/change-recovery", dependencies=[Depends(require_session)])
def change_recovery_credential(
    payload: RecoveryCredentialChangeRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(
            vault.change_recovery_credential(
                current_pin=payload.current_pin,
                new_recovery_secret=payload.new_recovery_secret,
                generate=payload.generate,
            )
        )
    except CredentialError as exc:
        raise credential_error(exc, "INVALID_CURRENT_PIN") from exc
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "RECOVERY_CREDENTIAL_CHANGE_FAILED",
                "message": str(exc),
            },
        ) from exc


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


@router.get("/backup/auto", dependencies=[Depends(require_session)])
def auto_backup_status(vault: Annotated[VaultManager, Depends(get_vault)]) -> dict:
    try:
        return envelope(vault.get_auto_backup_status())
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.put("/backup/auto", dependencies=[Depends(require_session)])
def update_auto_backup(
    payload: AutoBackupPolicyUpdateRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(
            vault.update_auto_backup_policy(
                enabled=payload.enabled,
                frequency=payload.frequency,
                retention_count=payload.retention_count,
                create_initial_backup=payload.create_initial_backup,
            )
        )
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "AUTO_BACKUP_POLICY_FAILED", "message": str(exc)},
        ) from exc


@router.post("/backup/auto/run", dependencies=[Depends(require_session)])
def run_auto_backup(vault: Annotated[VaultManager, Depends(get_vault)]) -> dict:
    try:
        return envelope(
            vault.create_automatic_backup(force=True, reason="manual-run")
        )
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "AUTO_BACKUP_FAILED", "message": str(exc)},
        ) from exc


@router.post("/backup/auto/verify-latest", dependencies=[Depends(require_session)])
def verify_latest_auto_backup(
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.verify_latest_auto_backup())
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "AUTO_BACKUP_VERIFY_FAILED",
                "message": str(exc),
            },
        ) from exc


@router.get("/backup/auto/history", dependencies=[Depends(require_session)])
def auto_backup_history(vault: Annotated[VaultManager, Depends(get_vault)]) -> dict:
    try:
        return envelope({"items": vault.list_auto_backup_history()})
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.post("/backup/auto/history/clear", dependencies=[Depends(require_session)])
def clear_auto_backup_history(
    payload: AutoBackupHistoryClearRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.clear_auto_backup_history())
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "AUTO_BACKUP_CLEAR_FAILED", "message": str(exc)},
        ) from exc


@router.get("/backup/auto/history/{filename}", dependencies=[Depends(require_session)])
def download_auto_backup(
    filename: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> FileResponse:
    try:
        path = vault.auto_backup_path(filename)
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "AUTO_BACKUP_NOT_FOUND", "message": str(exc)},
        ) from exc
    return FileResponse(
        path,
        media_type=LIFEVAULT_MEDIA_TYPE,
        filename=path.name,
        headers={"Cache-Control": "no-store"},
    )


@router.delete("/backup/auto/history/{filename}", dependencies=[Depends(require_session)])
def delete_auto_backup(
    filename: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.delete_auto_backup(filename=filename))
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "AUTO_BACKUP_NOT_FOUND", "message": str(exc)},
        ) from exc


@router.get("/backup/check", dependencies=[Depends(require_session)])
def check_backup(vault: Annotated[VaultManager, Depends(get_vault)]) -> dict:
    try:
        return envelope(vault.check_backup_integrity())
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "BACKUP_CHECK_FAILED", "message": str(exc)},
        ) from exc


@router.get("/backup/export", dependencies=[Depends(require_session)])
def export_backup(vault: Annotated[VaultManager, Depends(get_vault)]) -> Response:
    try:
        artifact = vault.export_lifevault(app_version=vault.app_version)
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "BACKUP_EXPORT_FAILED", "message": str(exc)},
        ) from exc
    return Response(
        content=artifact.content,
        media_type=LIFEVAULT_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            "X-LifeGraph-Backup-Format": "lifegraph-lifevault-v1",
            "Cache-Control": "no-store",
        },
    )


async def read_lifevault_upload(upload: UploadFile) -> bytes:
    filename = upload.filename or ""
    if filename and not filename.lower().endswith(".lifevault"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_BACKUP_FILE", "message": "请选择 .lifevault 备份文件"},
        )
    value = bytearray()
    while chunk := await upload.read(1024 * 1024):
        value.extend(chunk)
        if len(value) > MAX_LIFEVAULT_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={"code": "BACKUP_TOO_LARGE", "message": "备份文件超过 512 MB 限制"},
            )
    await upload.close()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_BACKUP_FILE", "message": "备份文件为空"},
        )
    return bytes(value)


@router.post("/backup/import/check", dependencies=[Depends(require_session)])
async def check_backup_import(
    vault: Annotated[VaultManager, Depends(get_vault)],
    backup_file: Annotated[UploadFile, File()],
    credential_method: Annotated[Literal["pin", "recovery"], Form()] = "pin",
    credential_secret: Annotated[str, Form(min_length=1, max_length=256)] = "",
) -> dict:
    content = await read_lifevault_upload(backup_file)
    try:
        return envelope(
            vault.inspect_lifevault_import(
                content=content,
                credential_method=credential_method,
                credential_secret=credential_secret,
            )
        )
    except CredentialError as exc:
        raise credential_error(exc, "INVALID_BACKUP_CREDENTIAL") from exc
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "BACKUP_IMPORT_CHECK_FAILED", "message": str(exc)},
        ) from exc


@router.post("/backup/import", dependencies=[Depends(require_session)])
async def import_backup(
    vault: Annotated[VaultManager, Depends(get_vault)],
    backup_file: Annotated[UploadFile, File()],
    credential_method: Annotated[Literal["pin", "recovery"], Form()] = "pin",
    credential_secret: Annotated[str, Form(min_length=1, max_length=256)] = "",
    confirm: Annotated[str, Form()] = "",
) -> dict:
    content = await read_lifevault_upload(backup_file)
    try:
        return envelope(
            vault.restore_lifevault(
                content=content,
                credential_method=credential_method,
                credential_secret=credential_secret,
                confirm=confirm,
                app_version=vault.app_version,
            )
        )
    except CredentialError as exc:
        raise credential_error(exc, "INVALID_BACKUP_CREDENTIAL") from exc
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "BACKUP_RESTORE_FAILED", "message": str(exc)},
        ) from exc


@router.post("/profile/change-impact", dependencies=[Depends(require_session)])
def profile_change_impact(
    payload: ProfileImpactRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.profile_change_impact(birth_date=payload.birth_date.isoformat()))
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PROFILE_IMPACT_FAILED", "message": str(exc)},
        ) from exc


@router.put("/profile", dependencies=[Depends(require_session)])
def update_profile(
    payload: ProfileUpdateRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(
            vault.update_profile(
                display_name=payload.display_name,
                birth_date=payload.birth_date.isoformat(),
                current_pin=payload.current_pin,
                revision=payload.revision,
            )
        )
    except CredentialError as exc:
        raise credential_error(exc, "INVALID_CURRENT_PIN") from exc
    except ContentNotFound as exc:
        raise content_not_found_error(exc) from exc
    except ContentRevisionConflict as exc:
        raise revision_conflict_error(exc) from exc
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PROFILE_UPDATE_FAILED", "message": str(exc)},
        ) from exc


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


@router.get("/content/browse", dependencies=[Depends(require_session)])
def browse_content(
    vault: Annotated[VaultManager, Depends(get_vault)],
    kind: Annotated[list[Literal["event", "memory", "plan"]] | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    sort: Annotated[Literal["date_desc", "date_asc", "updated_desc"], Query()] = "date_desc",
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_BROWSE_RANGE", "message": "开始日期不能晚于结束日期"},
        )
    try:
        return envelope(
            vault.browse_content(
                kinds=kind or ["event", "memory", "plan"],
                date_from=date_from.isoformat() if date_from else None,
                date_to=date_to.isoformat() if date_to else None,
                sort=sort,
                limit=limit,
            )
        )
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.get("/content/search", dependencies=[Depends(require_session)])
def search_content(
    vault: Annotated[VaultManager, Depends(get_vault)],
    q: Annotated[str, Query(max_length=120)] = "",
    kind: Annotated[list[Literal["event", "memory", "plan"]] | None, Query()] = None,
    tag_id: Annotated[list[str] | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    sort: Annotated[Literal["date_desc", "date_asc", "updated_desc"], Query()] = "date_desc",
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_SEARCH_RANGE", "message": "开始日期不能晚于结束日期"},
        )
    try:
        return envelope(
            vault.search_content(
                query=q,
                kinds=kind or ["event", "memory", "plan"],
                tag_ids=tag_id or [],
                date_from=date_from.isoformat() if date_from else None,
                date_to=date_to.isoformat() if date_to else None,
                sort=sort,
                limit=limit,
            )
        )
    except VaultError as exc:
        raise locked_error(exc) from exc


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


@router.put("/events/{event_id}", dependencies=[Depends(require_session)])
def update_event(
    event_id: str,
    payload: ContentUpdateRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(
            vault.update_event(
                event_id=event_id,
                title=payload.title,
                content=payload.content,
                revision=payload.revision,
            )
        )
    except ContentNotFound as exc:
        raise content_not_found_error(exc) from exc
    except ContentRevisionConflict as exc:
        raise revision_conflict_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.delete("/events/{event_id}", dependencies=[Depends(require_session)])
def delete_event(
    event_id: str,
    payload: ContentDeleteRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.delete_event(event_id=event_id, revision=payload.revision))
    except ContentNotFound as exc:
        raise content_not_found_error(exc) from exc
    except ContentRevisionConflict as exc:
        raise revision_conflict_error(exc) from exc
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
            content_format=payload.content_format,
        )
        return envelope(memory)
    except DateOutOfLifeRange as exc:
        raise date_range_error(exc) from exc
    except ValueError as exc:
        raise invalid_period_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.put("/memories/{memory_id}", dependencies=[Depends(require_session)])
def update_memory(
    memory_id: str,
    payload: ContentUpdateRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(
            vault.update_memory(
                memory_id=memory_id,
                title=payload.title,
                content=payload.content,
                content_format=payload.content_format,
                revision=payload.revision,
            )
        )
    except ContentNotFound as exc:
        raise content_not_found_error(exc) from exc
    except ContentRevisionConflict as exc:
        raise revision_conflict_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.delete("/memories/{memory_id}", dependencies=[Depends(require_session)])
def delete_memory(
    memory_id: str,
    payload: ContentDeleteRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.delete_memory(memory_id=memory_id, revision=payload.revision))
    except ContentNotFound as exc:
        raise content_not_found_error(exc) from exc
    except ContentRevisionConflict as exc:
        raise revision_conflict_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc




@router.get("/content/tag-map", dependencies=[Depends(require_session)])
def content_tag_map(
    vault: Annotated[VaultManager, Depends(get_vault)],
    start: Annotated[date, Query()],
    end: Annotated[date, Query()],
    tag_id: Annotated[list[str] | None, Query()] = None,
    kind: Annotated[list[Literal["event", "memory", "plan"]] | None, Query()] = None,
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
    if not tag_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TAG_FILTER_REQUIRED", "message": "请至少选择一个标签"},
        )
    try:
        return envelope(
            vault.get_content_tag_map(
                tag_ids=tag_id,
                start_date=start.isoformat(),
                end_date=end.isoformat(),
                kinds=kind or ["event", "memory", "plan"],
            )
        )
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.get("/memories/search", dependencies=[Depends(require_session)])
def search_memories(
    vault: Annotated[VaultManager, Depends(get_vault)],
    q: Annotated[str, Query(max_length=120)] = "",
    tag_id: Annotated[list[str] | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_SEARCH_RANGE", "message": "开始日期不能晚于结束日期"},
        )
    try:
        return envelope(
            vault.search_memories(
                query=q,
                tag_ids=tag_id or [],
                date_from=date_from.isoformat() if date_from else None,
                date_to=date_to.isoformat() if date_to else None,
                limit=limit,
            )
        )
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.get("/memories/tag-map", dependencies=[Depends(require_session)])
def memory_tag_map(
    vault: Annotated[VaultManager, Depends(get_vault)],
    start: Annotated[date, Query()],
    end: Annotated[date, Query()],
    tag_id: Annotated[list[str] | None, Query()] = None,
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
    if not tag_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TAG_FILTER_REQUIRED", "message": "请至少选择一个标签"},
        )
    try:
        return envelope(
            vault.get_memory_tag_map(
                tag_ids=tag_id,
                start_date=start.isoformat(),
                end_date=end.isoformat(),
            )
        )
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.get("/tags", dependencies=[Depends(require_session)])
def list_tags(
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.list_tags())
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.post("/tags", dependencies=[Depends(require_session)])
def create_tag(
    payload: TagCreateRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.create_tag(name=payload.name, color=payload.color))
    except TagConflict as exc:
        raise tag_conflict_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.put("/tags/{tag_id}", dependencies=[Depends(require_session)])
def update_tag(
    tag_id: str,
    payload: TagUpdateRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.update_tag(tag_id=tag_id, name=payload.name, color=payload.color))
    except TagConflict as exc:
        raise tag_conflict_error(exc) from exc
    except ContentNotFound as exc:
        raise content_not_found_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.delete("/tags/{tag_id}", dependencies=[Depends(require_session)])
def delete_tag(
    tag_id: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.delete_tag(tag_id=tag_id))
    except ContentNotFound as exc:
        raise content_not_found_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.post("/content/bulk/tags", dependencies=[Depends(require_session)])
def bulk_update_content_tags(
    payload: ContentBulkTagRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        items = [item.model_dump() for item in payload.items]
        return envelope(
            vault.bulk_update_content_tags(
                items=items, tag_ids=payload.tag_ids, operation=payload.operation
            )
        )
    except ContentNotFound as exc:
        raise content_not_found_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.get("/content/{kind}/{content_id}/tags", dependencies=[Depends(require_session)])
def list_content_tags(
    kind: Literal["event", "memory", "plan"],
    content_id: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.list_content_tags(kind=kind, content_id=content_id))
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.put("/content/{kind}/{content_id}/tags", dependencies=[Depends(require_session)])
def replace_content_tags(
    kind: Literal["event", "memory", "plan"],
    content_id: str,
    payload: ContentTagSelectionRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(
            vault.replace_content_tags(
                kind=kind, content_id=content_id, tag_ids=payload.tag_ids
            )
        )
    except ContentNotFound as exc:
        raise content_not_found_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.post("/content/{kind}/{content_id}/tags/{tag_id}", dependencies=[Depends(require_session)])
def attach_content_tag(
    kind: Literal["event", "memory", "plan"],
    content_id: str,
    tag_id: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        vault.attach_content_tag(kind=kind, content_id=content_id, tag_id=tag_id)
        return envelope({"attached": True})
    except ContentNotFound as exc:
        raise content_not_found_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.delete("/content/{kind}/{content_id}/tags/{tag_id}", dependencies=[Depends(require_session)])
def detach_content_tag(
    kind: Literal["event", "memory", "plan"],
    content_id: str,
    tag_id: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        vault.detach_content_tag(kind=kind, content_id=content_id, tag_id=tag_id)
        return envelope({"detached": True})
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.get("/memories/{memory_id}/tags", dependencies=[Depends(require_session)])
def list_memory_tags(
    memory_id: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.list_memory_tags(memory_id=memory_id))
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.post("/memories/{memory_id}/tags/{tag_id}", dependencies=[Depends(require_session)])
def attach_memory_tag(
    memory_id: str,
    tag_id: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        vault.attach_memory_tag(memory_id=memory_id, tag_id=tag_id)
        return envelope({"attached": True})
    except ContentNotFound as exc:
        raise content_not_found_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.delete("/memories/{memory_id}/tags/{tag_id}", dependencies=[Depends(require_session)])
def detach_memory_tag(
    memory_id: str,
    tag_id: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        vault.detach_memory_tag(memory_id=memory_id, tag_id=tag_id)
        return envelope({"detached": True})
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


@router.put("/plans/{plan_id}", dependencies=[Depends(require_session)])
def update_plan(
    plan_id: str,
    payload: ContentUpdateRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(
            vault.update_plan(
                plan_id=plan_id,
                title=payload.title,
                content=payload.content,
                revision=payload.revision,
            )
        )
    except ContentNotFound as exc:
        raise content_not_found_error(exc) from exc
    except ContentRevisionConflict as exc:
        raise revision_conflict_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.delete("/plans/{plan_id}", dependencies=[Depends(require_session)])
def delete_plan(
    plan_id: str,
    payload: ContentDeleteRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.delete_plan(plan_id=plan_id, revision=payload.revision))
    except ContentNotFound as exc:
        raise content_not_found_error(exc) from exc
    except ContentRevisionConflict as exc:
        raise revision_conflict_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc

@router.get("/trash", dependencies=[Depends(require_session)])
def list_trash(vault: Annotated[VaultManager, Depends(get_vault)]) -> dict:
    try:
        items = vault.list_trash()
        counts = {"event": 0, "memory": 0, "plan": 0}
        for item in items:
            counts[item["kind"]] += 1
        return envelope({"items": items, "counts": counts, "total": len(items)})
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.post("/trash/{kind}/{content_id}/restore", dependencies=[Depends(require_session)])
def restore_trash_item(
    kind: Literal["event", "memory", "plan"],
    content_id: str,
    payload: ContentDeleteRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(
            vault.restore_trash_item(
                kind=kind,
                content_id=content_id,
                revision=payload.revision,
            )
        )
    except ContentNotFound as exc:
        raise content_not_found_error(exc) from exc
    except ContentRevisionConflict as exc:
        raise revision_conflict_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.delete("/trash/{kind}/{content_id}", dependencies=[Depends(require_session)])
def permanently_delete_trash_item(
    kind: Literal["event", "memory", "plan"],
    content_id: str,
    payload: ContentDeleteRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(
            vault.permanently_delete_trash_item(
                kind=kind,
                content_id=content_id,
                revision=payload.revision,
            )
        )
    except ContentNotFound as exc:
        raise content_not_found_error(exc) from exc
    except ContentRevisionConflict as exc:
        raise revision_conflict_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.delete("/trash", dependencies=[Depends(require_session)])
def empty_trash(
    payload: TrashClearRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.empty_trash())
    except VaultError as exc:
        raise locked_error(exc) from exc

