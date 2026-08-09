from __future__ import annotations

from datetime import date
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import quote
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from app.models import (
    AutoBackupHistoryClearRequest,
    AutoBackupPolicyUpdateRequest,
    ContentDeleteRequest,
    ContentMoveRequest,
    ContentBulkTagRequest,
    ContentTagSelectionRequest,
    ContentUpdateRequest,
    EventCreateRequest,
    InitializeRequest,
    MemoryCreateRequest,
    MaterialDuplicateCheckRequest,
    LargeMaterialUploadInitRequest,
    LargeMaterialVideoMetadataRequest,
    LargeUploadCleanupRequest,
    MediaBackupJobRequest,
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
    MaterialDuplicate,
    VaultError,
    VaultManager,
)
from app.services.attachments import MAX_ATTACHMENT_BYTES
from app.services.large_files import MAX_MEDIA_CHUNK_SIZE
from app.services.media_previews import MAX_MEDIA_PREVIEW_BYTES
from app.services.backup import LIFEVAULT_MEDIA_TYPE, MAX_LIFEVAULT_IMPORT_BYTES
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


def parse_video_metadata_form(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_VIDEO_METADATA", "message": "视频元数据格式无效"},
        ) from exc
    if not isinstance(value, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_VIDEO_METADATA", "message": "视频元数据必须为对象"},
        )
    return value




def parse_http_byte_range(range_header: str | None, total_size: int) -> tuple[int, int, bool]:
    """Parse one RFC 7233 byte range and return [start, end_exclusive)."""
    total_size = int(total_size)
    if total_size <= 0:
        raise ValueError("invalid total size")
    value = str(range_header or "").strip()
    if not value:
        return 0, total_size, False
    if not value.lower().startswith("bytes=") or "," in value:
        raise ValueError("unsupported byte range")
    spec = value.split("=", 1)[1].strip()
    if "-" not in spec:
        raise ValueError("invalid byte range")
    start_text, end_text = (part.strip() for part in spec.split("-", 1))
    if not start_text:
        if not end_text.isdigit():
            raise ValueError("invalid suffix range")
        suffix = int(end_text)
        if suffix <= 0:
            raise ValueError("invalid suffix range")
        start = max(0, total_size - suffix)
        return start, total_size, True
    if not start_text.isdigit():
        raise ValueError("invalid range start")
    start = int(start_text)
    if start >= total_size:
        raise ValueError("range starts past end")
    if not end_text:
        return start, total_size, True
    if not end_text.isdigit():
        raise ValueError("invalid range end")
    end_inclusive = min(int(end_text), total_size - 1)
    if end_inclusive < start:
        raise ValueError("range end before start")
    return start, end_inclusive + 1, True

async def read_optional_preview(preview_file: UploadFile | None) -> tuple[bytes | None, str | None]:
    if preview_file is None:
        return None, None
    content = await preview_file.read(MAX_MEDIA_PREVIEW_BYTES + 1)
    if len(content) > MAX_MEDIA_PREVIEW_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={"code": "VIDEO_PREVIEW_TOO_LARGE", "message": "视频封面不能超过 512 KB"},
        )
    return content or None, preview_file.content_type


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
    materials = vault.list_materials_for_period(scope=scope, period_key=period_key)
    for kind, items in (("event", events), ("memory", memories), ("plan", plans)):
        content_ids = [item["id"] for item in items]
        tags_by_content = vault.list_content_tags_for_items(
            kind=kind, content_ids=content_ids
        )
        attachment_counts = vault.list_attachment_counts_for_items(
            kind=kind, content_ids=content_ids
        )
        for item in items:
            item["tags"] = tags_by_content.get(item["id"], [])
            item["attachment_count"] = attachment_counts.get(item["id"], 0)
    content_state = {
        "has_event": bool(events),
        "has_memory": bool(memories),
        "has_plan": bool(plans),
    }
    if materials:
        content_state["has_material"] = True
    description.update(
        {
            "content_state": content_state,
            "events": events,
            "memories": memories,
            "plans": plans,
            "materials": materials,
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
            "storage_mode": "sqlite+aead-field-encryption+encrypted-attachments",
            "large_media": {
                "foundation": "chunked-v1",
                "root": "media",
                "api_enabled": False,
            },
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


@router.get("/backup/auto/reminder", dependencies=[Depends(require_session)])
def auto_backup_reminder_status(vault: Annotated[VaultManager, Depends(get_vault)]) -> dict:
    try:
        return envelope(vault.get_auto_backup_reminder_status())
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


@router.get("/backup/media/status", dependencies=[Depends(require_session)])
def media_backup_status(vault: Annotated[VaultManager, Depends(get_vault)]) -> dict:
    try:
        return envelope(vault.media_library_status(include_items=False))
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "MEDIA_BACKUP_STATUS_FAILED", "message": str(exc)},
        ) from exc


@router.get("/backup/media/job", dependencies=[Depends(require_session)])
def media_backup_job_status(vault: Annotated[VaultManager, Depends(get_vault)]) -> dict:
    try:
        return envelope(vault.media_backup_job_status())
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MEDIA_BACKUP_JOB_STATUS_FAILED", "message": str(exc)},
        ) from exc


@router.post("/backup/media/sync", dependencies=[Depends(require_session)])
def start_media_backup_sync(
    payload: MediaBackupJobRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.start_media_backup_job(target_path=payload.target_path, mode="sync"))
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MEDIA_BACKUP_SYNC_FAILED", "message": str(exc)},
        ) from exc


@router.post("/backup/media/verify", dependencies=[Depends(require_session)])
def start_media_backup_verify(
    payload: MediaBackupJobRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.start_media_backup_job(target_path=payload.target_path, mode="verify"))
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MEDIA_BACKUP_VERIFY_FAILED", "message": str(exc)},
        ) from exc


@router.post("/backup/media/verify-library", dependencies=[Depends(require_session)])
def start_media_library_verify(
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.start_media_backup_job(mode="source-verify"))
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MEDIA_LIBRARY_VERIFY_FAILED", "message": str(exc)},
        ) from exc


@router.post("/backup/media/cancel", dependencies=[Depends(require_session)])
def cancel_media_backup_job(vault: Annotated[VaultManager, Depends(get_vault)]) -> dict:
    try:
        return envelope(vault.cancel_media_backup_job())
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MEDIA_BACKUP_CANCEL_FAILED", "message": str(exc)},
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
        artifact = vault.export_lifevault_file(app_version=vault.app_version)
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "BACKUP_EXPORT_FAILED", "message": str(exc)},
        ) from exc

    def cleanup_export() -> None:
        artifact.path.unlink(missing_ok=True)
        try:
            artifact.path.parent.rmdir()
        except OSError:
            pass

    return FileResponse(
        path=artifact.path,
        filename=artifact.filename,
        media_type=LIFEVAULT_MEDIA_TYPE,
        headers={
            "X-LifeGraph-Backup-Format": "lifegraph-lifevault-v3",
            "Cache-Control": "no-store",
        },
        background=BackgroundTask(cleanup_export),
    )


async def read_lifevault_upload(upload: UploadFile) -> Path:
    filename = upload.filename or ""
    if filename and not filename.lower().endswith(".lifevault"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_BACKUP_FILE", "message": "请选择 .lifevault 备份文件"},
        )
    fd, temp_name = tempfile.mkstemp(prefix="lifegraph-import-", suffix=".lifevault")
    os.close(fd)
    path = Path(temp_name)
    size = 0
    try:
        with path.open("wb") as stream:
            while chunk := await upload.read(1024 * 1024):
                stream.write(chunk)
                size += len(chunk)
                if size > MAX_LIFEVAULT_IMPORT_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail={"code": "BACKUP_TOO_LARGE", "message": "备份文件超过 2 TB 安全限制"},
                    )
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    if size <= 0:
        path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_BACKUP_FILE", "message": "备份文件为空"},
        )
    return path


@router.post("/backup/import/check", dependencies=[Depends(require_session)])
async def check_backup_import(
    vault: Annotated[VaultManager, Depends(get_vault)],
    backup_file: Annotated[UploadFile, File()],
    credential_method: Annotated[Literal["pin", "recovery"], Form()] = "pin",
    credential_secret: Annotated[str, Form(min_length=1, max_length=256)] = "",
) -> dict:
    path = await read_lifevault_upload(backup_file)
    try:
        return envelope(
            vault.inspect_lifevault_import_file(
                path=path,
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
    finally:
        path.unlink(missing_ok=True)


@router.post("/backup/import", dependencies=[Depends(require_session)])
async def import_backup(
    vault: Annotated[VaultManager, Depends(get_vault)],
    backup_file: Annotated[UploadFile, File()],
    credential_method: Annotated[Literal["pin", "recovery"], Form()] = "pin",
    credential_secret: Annotated[str, Form(min_length=1, max_length=256)] = "",
    confirm: Annotated[str, Form()] = "",
) -> dict:
    path = await read_lifevault_upload(backup_file)
    try:
        return envelope(
            vault.restore_lifevault_file(
                path=path,
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
    finally:
        path.unlink(missing_ok=True)


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


@router.post("/materials/import", dependencies=[Depends(require_session)])
async def import_material(
    material_file: Annotated[UploadFile, File()],
    vault: Annotated[VaultManager, Depends(get_vault)],
    file_last_modified_ms: Annotated[int | None, Form()] = None,
    source_relative_path: Annotated[str | None, Form(max_length=1000)] = None,
    source_directory_name: Annotated[str | None, Form(max_length=120)] = None,
    reject_duplicate: Annotated[bool, Form()] = False,
    video_metadata_json: Annotated[str | None, Form(max_length=2000)] = None,
    video_preview: Annotated[UploadFile | None, File()] = None,
) -> dict:
    content = await material_file.read(MAX_ATTACHMENT_BYTES + 1)
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={"code": "MATERIAL_TOO_LARGE", "message": "单个资料不能超过 50 MB"},
        )
    preview_content, preview_media_type = await read_optional_preview(video_preview)
    try:
        return envelope(
            vault.import_material(
                filename=material_file.filename or "未命名资料",
                media_type=material_file.content_type,
                content=content,
                file_last_modified_ms=file_last_modified_ms,
                source_relative_path=source_relative_path,
                source_directory_name=source_directory_name,
                reject_duplicate=reject_duplicate,
                video_metadata=parse_video_metadata_form(video_metadata_json),
                preview_content=preview_content,
                preview_media_type=preview_media_type,
            )
        )
    except MaterialDuplicate as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "MATERIAL_DUPLICATE", "message": str(exc)},
        ) from exc
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MATERIAL_IMPORT_FAILED", "message": str(exc)},
        ) from exc


@router.get("/materials/large/uploads/maintenance", dependencies=[Depends(require_session)])
def large_upload_maintenance_status(
    vault: Annotated[VaultManager, Depends(get_vault)],
    stale_days: Annotated[int, Query(ge=7, le=365)] = 30,
) -> dict:
    try:
        return envelope(vault.large_upload_maintenance_status(stale_days=stale_days))
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "LARGE_UPLOAD_MAINTENANCE_FAILED", "message": str(exc)},
        ) from exc


@router.post("/materials/large/uploads/cleanup", dependencies=[Depends(require_session)])
def cleanup_stale_large_uploads(
    payload: LargeUploadCleanupRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.cleanup_stale_large_uploads(stale_days=payload.stale_days))
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "LARGE_UPLOAD_CLEANUP_FAILED", "message": str(exc)},
        ) from exc


@router.post("/materials/large/uploads", dependencies=[Depends(require_session)])
def create_large_material_upload(
    payload: LargeMaterialUploadInitRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(
            vault.create_large_material_upload(
                filename=payload.filename,
                media_type=payload.media_type,
                size_bytes=payload.size_bytes,
                chunk_size=payload.chunk_size,
                file_last_modified_ms=payload.file_last_modified_ms,
                source_relative_path=payload.source_relative_path,
                source_directory_name=payload.source_directory_name,
                quick_fingerprint=payload.quick_fingerprint,
                reject_duplicate=payload.reject_duplicate,
            )
        )
    except MaterialDuplicate as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "MATERIAL_DUPLICATE", "message": str(exc)},
        ) from exc
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "LARGE_UPLOAD_INIT_FAILED", "message": str(exc)},
        ) from exc


@router.get("/materials/large/uploads/{session_id}", dependencies=[Depends(require_session)])
def get_large_material_upload(
    session_id: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.get_large_material_upload(session_id=session_id))
    except ContentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "LARGE_UPLOAD_NOT_FOUND", "message": str(exc)},
        ) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.put("/materials/large/uploads/{session_id}/video-metadata", dependencies=[Depends(require_session)])
def update_large_material_video_metadata(
    session_id: str,
    payload: LargeMaterialVideoMetadataRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(
            vault.update_large_material_video_metadata(
                session_id=session_id,
                metadata=payload.model_dump(exclude_none=True),
            )
        )
    except ContentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "LARGE_UPLOAD_NOT_FOUND", "message": str(exc)},
        ) from exc
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VIDEO_METADATA_UPDATE_FAILED", "message": str(exc)},
        ) from exc


@router.put("/materials/large/uploads/{session_id}/preview", dependencies=[Depends(require_session)])
async def upload_large_material_preview(
    session_id: str,
    request: Request,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    content = bytearray()
    async for part in request.stream():
        if not part:
            continue
        if len(content) + len(part) > MAX_MEDIA_PREVIEW_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail={"code": "VIDEO_PREVIEW_TOO_LARGE", "message": "视频封面不能超过 512 KB"},
            )
        content.extend(part)
    try:
        return envelope(
            vault.put_large_material_preview(
                session_id=session_id,
                content=bytes(content),
                media_type=request.headers.get("content-type"),
            )
        )
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VIDEO_PREVIEW_UPLOAD_FAILED", "message": str(exc)},
        ) from exc


@router.put("/materials/large/uploads/{session_id}/chunks/{index}", dependencies=[Depends(require_session)])
async def upload_large_material_chunk(
    session_id: str,
    index: int,
    request: Request,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    if index < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_CHUNK_INDEX", "message": "分块序号不能小于 0"},
        )
    content = bytearray()
    async for part in request.stream():
        if not part:
            continue
        if len(content) + len(part) > MAX_MEDIA_CHUNK_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail={"code": "CHUNK_TOO_LARGE", "message": "单个上传分块不能超过 32 MB"},
            )
        content.extend(part)
    try:
        result = await run_in_threadpool(
            vault.put_large_material_chunk,
            session_id=session_id,
            index=index,
            content=bytes(content),
        )
        return envelope(result)
    except MaterialDuplicate as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "LARGE_UPLOAD_CHUNK_CONFLICT", "message": str(exc)},
        ) from exc
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "LARGE_UPLOAD_CHUNK_FAILED", "message": str(exc)},
        ) from exc


@router.delete("/materials/large/uploads/{session_id}", dependencies=[Depends(require_session)])
def cancel_large_material_upload(
    session_id: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.cancel_large_material_upload(session_id=session_id))
    except ContentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "LARGE_UPLOAD_NOT_FOUND", "message": str(exc)},
        ) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.post("/materials/large/uploads/{session_id}/finalize", dependencies=[Depends(require_session)])
def finalize_large_material_upload(
    session_id: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.finalize_large_material_upload(session_id=session_id))
    except MaterialDuplicate as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "MATERIAL_DUPLICATE", "message": str(exc)},
        ) from exc
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "LARGE_UPLOAD_FINALIZE_FAILED", "message": str(exc)},
        ) from exc


@router.post("/materials/duplicates", dependencies=[Depends(require_session)])
def check_material_duplicates(
    payload: MaterialDuplicateCheckRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.find_material_duplicates(payload.sha256))
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.get("/materials/browse", dependencies=[Depends(require_session)])
def browse_materials(
    vault: Annotated[VaultManager, Depends(get_vault)],
    q: Annotated[str, Query(max_length=120)] = "",
    category: Annotated[list[Literal["image", "video", "document", "other"]] | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    sort: Annotated[Literal["timeline_desc", "timeline_asc", "added_desc"], Query()] = "timeline_desc",
    limit: Annotated[int, Query(ge=1, le=100)] = 48,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> dict:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_MATERIAL_RANGE", "message": "资料开始日期不能晚于结束日期"},
        )
    try:
        return envelope(
            vault.browse_materials(
                query=q,
                categories=category or ["image", "document", "other"],
                date_from=date_from.isoformat() if date_from else None,
                date_to=date_to.isoformat() if date_to else None,
                sort=sort,
                limit=limit,
                offset=offset,
            )
        )
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.delete("/materials/{attachment_id}", dependencies=[Depends(require_session)])
def delete_independent_material(
    attachment_id: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.delete_independent_material(attachment_id=attachment_id))
    except ContentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "MATERIAL_NOT_FOUND", "message": str(exc)},
        ) from exc
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


@router.put("/content/{kind}/{content_id}/period", dependencies=[Depends(require_session)])
def move_content_period(
    kind: Literal["event", "memory", "plan"],
    content_id: str,
    payload: ContentMoveRequest,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        description = resolve_payload_target(vault, payload.time_scope, payload.period_key)
        if kind == "plan" and not description["plan_allowed"]:
            code = "PLAN_DATE_IN_PAST" if payload.time_scope == "day" else "PLAN_PERIOD_IN_PAST"
            message = "未来计划不能移动到已经过去的日期" if payload.time_scope == "day" else "未来计划不能移动到已经结束的时间范围"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": code, "message": message},
            )
        return envelope(
            vault.move_content_period(
                kind=kind,
                content_id=content_id,
                anchor_date=description["anchor_date"],
                time_scope=payload.time_scope,
                period_key=payload.period_key,
                revision=payload.revision,
            )
        )
    except DateOutOfLifeRange as exc:
        raise date_range_error(exc) from exc
    except ValueError as exc:
        raise invalid_period_error(exc) from exc
    except ContentNotFound as exc:
        raise content_not_found_error(exc) from exc
    except ContentRevisionConflict as exc:
        raise revision_conflict_error(exc) from exc
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


@router.get("/content/{kind}/{content_id}/attachments", dependencies=[Depends(require_session)])
def list_content_attachments(
    kind: Literal["event", "memory", "plan"],
    content_id: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.list_attachments(kind=kind, content_id=content_id))
    except ContentNotFound as exc:
        raise content_not_found_error(exc) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.post("/content/{kind}/{content_id}/attachments", dependencies=[Depends(require_session)])
async def upload_content_attachment(
    kind: Literal["event", "memory", "plan"],
    content_id: str,
    attachment_file: Annotated[UploadFile, File()],
    vault: Annotated[VaultManager, Depends(get_vault)],
    file_last_modified_ms: Annotated[int | None, Form()] = None,
    video_metadata_json: Annotated[str | None, Form(max_length=2000)] = None,
    video_preview: Annotated[UploadFile | None, File()] = None,
) -> dict:
    content = await attachment_file.read(MAX_ATTACHMENT_BYTES + 1)
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={"code": "ATTACHMENT_TOO_LARGE", "message": "单个附件不能超过 50 MB"},
        )
    preview_content, preview_media_type = await read_optional_preview(video_preview)
    try:
        return envelope(
            vault.create_attachment(
                kind=kind,
                content_id=content_id,
                filename=attachment_file.filename or "未命名附件",
                media_type=attachment_file.content_type,
                content=content,
                file_last_modified_ms=file_last_modified_ms,
                video_metadata=parse_video_metadata_form(video_metadata_json),
                preview_content=preview_content,
                preview_media_type=preview_media_type,
            )
        )
    except ContentNotFound as exc:
        raise content_not_found_error(exc) from exc
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "ATTACHMENT_UPLOAD_FAILED", "message": str(exc)},
        ) from exc


@router.get("/attachments/{attachment_id}/download", dependencies=[Depends(require_session)])
def download_attachment(
    attachment_id: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> Response:
    try:
        metadata, content = vault.read_attachment(attachment_id=attachment_id)
    except ContentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ATTACHMENT_NOT_FOUND", "message": str(exc)},
        ) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc
    filename = str(metadata.get("filename") or "attachment")
    encoded = quote(filename, safe="")
    return Response(
        content=content,
        media_type=str(metadata.get("media_type") or "application/octet-stream"),
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
            "X-LifeGraph-Attachment-Id": attachment_id,
        },
    )


@router.post("/attachments/{attachment_id}/playback-ticket", dependencies=[Depends(require_session)])
def create_attachment_playback_ticket(
    attachment_id: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.create_attachment_playback_ticket(attachment_id=attachment_id))
    except ContentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ATTACHMENT_NOT_FOUND", "message": str(exc)},
        ) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


def _attachment_stream_response(
    *,
    attachment_id: str,
    ticket: str,
    range_header: str | None,
    download: bool,
    vault: VaultManager,
    head_only: bool = False,
) -> Response:
    if not vault.sessions.validate_media_ticket(ticket, attachment_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "MEDIA_TICKET_INVALID", "message": "视频播放凭据已失效，请重新打开视频"},
        )
    try:
        metadata = vault.get_attachment_stream_metadata(attachment_id=attachment_id)
    except ContentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ATTACHMENT_NOT_FOUND", "message": str(exc)},
        ) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc

    total_size = int(metadata.get("size_bytes") or 0)
    try:
        start, end_exclusive, partial = parse_http_byte_range(range_header, total_size)
    except ValueError:
        return Response(
            status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes */{total_size}",
                "Cache-Control": "private, no-store",
            },
        )

    filename = str(metadata.get("filename") or "attachment")
    encoded = quote(filename, safe="")
    content_length = end_exclusive - start
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Disposition": f"{'attachment' if download else 'inline'}; filename*=UTF-8''{encoded}",
        "Cache-Control": "private, no-store",
        "X-LifeGraph-Attachment-Id": attachment_id,
    }
    status_code = status.HTTP_206_PARTIAL_CONTENT if partial else status.HTTP_200_OK
    if partial:
        headers["Content-Range"] = f"bytes {start}-{end_exclusive - 1}/{total_size}"
    if head_only:
        return Response(
            status_code=status_code,
            media_type=str(metadata.get("media_type") or "application/octet-stream"),
            headers=headers,
        )
    try:
        iterator = vault.iter_attachment_stream_range(
            attachment_id=attachment_id,
            start=start,
            end_exclusive=end_exclusive,
        )
    except ContentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ATTACHMENT_NOT_FOUND", "message": str(exc)},
        ) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc
    return StreamingResponse(
        iterator,
        status_code=status_code,
        media_type=str(metadata.get("media_type") or "application/octet-stream"),
        headers=headers,
    )


@router.get("/attachments/{attachment_id}/stream")
def stream_attachment(
    attachment_id: str,
    ticket: Annotated[str, Query(min_length=20, max_length=200)],
    vault: Annotated[VaultManager, Depends(get_vault)],
    range_header: Annotated[str | None, Header(alias="Range")] = None,
    download: bool = False,
) -> Response:
    return _attachment_stream_response(
        attachment_id=attachment_id,
        ticket=ticket,
        range_header=range_header,
        download=download,
        vault=vault,
    )


@router.head("/attachments/{attachment_id}/stream")
def head_stream_attachment(
    attachment_id: str,
    ticket: Annotated[str, Query(min_length=20, max_length=200)],
    vault: Annotated[VaultManager, Depends(get_vault)],
    range_header: Annotated[str | None, Header(alias="Range")] = None,
    download: bool = False,
) -> Response:
    return _attachment_stream_response(
        attachment_id=attachment_id,
        ticket=ticket,
        range_header=range_header,
        download=download,
        vault=vault,
        head_only=True,
    )


@router.get("/attachments/{attachment_id}/audio-compat", dependencies=[Depends(require_session)])
def attachment_audio_compat_status(
    attachment_id: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.get_attachment_audio_compat_status(attachment_id=attachment_id))
    except ContentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ATTACHMENT_NOT_FOUND", "message": str(exc)},
        ) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc


@router.post("/attachments/{attachment_id}/audio-compat", dependencies=[Depends(require_session)])
def start_attachment_audio_compat(
    attachment_id: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.start_attachment_audio_compat(attachment_id=attachment_id))
    except ContentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ATTACHMENT_NOT_FOUND", "message": str(exc)},
        ) from exc
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "AUDIO_COMPAT_UNAVAILABLE", "message": str(exc)},
        ) from exc


def _attachment_audio_compat_stream_response(
    *,
    attachment_id: str,
    ticket: str,
    range_header: str | None,
    vault: VaultManager,
    head_only: bool = False,
) -> Response:
    if not vault.sessions.validate_media_ticket(ticket, attachment_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "MEDIA_TICKET_INVALID", "message": "视频播放凭据已失效，请重新打开视频"},
        )
    try:
        metadata = vault.get_attachment_audio_compat_stream_metadata(attachment_id=attachment_id)
    except ContentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "AUDIO_COMPAT_NOT_FOUND", "message": str(exc)},
        ) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc

    total_size = int(metadata.get("size_bytes") or 0)
    try:
        start, end_exclusive, partial = parse_http_byte_range(range_header, total_size)
    except ValueError:
        return Response(
            status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes */{total_size}",
                "Cache-Control": "private, no-store",
            },
        )
    media_type = str(metadata.get("media_type") or "audio/mp4")
    codec = str(metadata.get("audio_codec") or "AAC").strip().lower()
    fallback_name = "browser-audio.mp3" if media_type == "audio/mpeg" else "browser-audio.m4a"
    encoded = quote(str(metadata.get("filename") or fallback_name), safe="")
    content_length = end_exclusive - start
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Disposition": f"inline; filename*=UTF-8''{encoded}",
        "Cache-Control": "private, no-store",
        "X-LifeGraph-Attachment-Id": attachment_id,
        "X-LifeGraph-Audio-Compat": codec or "compat",
    }
    status_code = status.HTTP_206_PARTIAL_CONTENT if partial else status.HTTP_200_OK
    if partial:
        headers["Content-Range"] = f"bytes {start}-{end_exclusive - 1}/{total_size}"
    if head_only:
        return Response(
            status_code=status_code,
            media_type=media_type,
            headers=headers,
        )
    try:
        iterator = vault.iter_attachment_audio_compat_range(
            attachment_id=attachment_id,
            start=start,
            end_exclusive=end_exclusive,
        )
    except ContentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "AUDIO_COMPAT_NOT_FOUND", "message": str(exc)},
        ) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc
    return StreamingResponse(
        iterator,
        status_code=status_code,
        media_type=media_type,
        headers=headers,
    )


@router.get("/attachments/{attachment_id}/audio-compat/stream")
def stream_attachment_audio_compat(
    attachment_id: str,
    ticket: Annotated[str, Query(min_length=20, max_length=200)],
    vault: Annotated[VaultManager, Depends(get_vault)],
    range_header: Annotated[str | None, Header(alias="Range")] = None,
) -> Response:
    return _attachment_audio_compat_stream_response(
        attachment_id=attachment_id,
        ticket=ticket,
        range_header=range_header,
        vault=vault,
    )


@router.head("/attachments/{attachment_id}/audio-compat/stream")
def head_stream_attachment_audio_compat(
    attachment_id: str,
    ticket: Annotated[str, Query(min_length=20, max_length=200)],
    vault: Annotated[VaultManager, Depends(get_vault)],
    range_header: Annotated[str | None, Header(alias="Range")] = None,
) -> Response:
    return _attachment_audio_compat_stream_response(
        attachment_id=attachment_id,
        ticket=ticket,
        range_header=range_header,
        vault=vault,
        head_only=True,
    )


@router.get("/attachments/{attachment_id}/preview", dependencies=[Depends(require_session)])
def preview_attachment(
    attachment_id: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> Response:
    try:
        metadata, content = vault.read_attachment_preview(attachment_id=attachment_id)
    except ContentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ATTACHMENT_PREVIEW_NOT_FOUND", "message": str(exc)},
        ) from exc
    except VaultError as exc:
        raise locked_error(exc) from exc
    return Response(
        content=content,
        media_type=str(metadata.get("preview_media_type") or "image/jpeg"),
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.post("/attachments/{attachment_id}/timeline-fallback", dependencies=[Depends(require_session)])
def assign_attachment_timeline_fallback(
    attachment_id: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(vault.assign_attachment_timeline_fallback(attachment_id=attachment_id))
    except ContentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ATTACHMENT_NOT_FOUND", "message": str(exc)},
        ) from exc
    except VaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "ATTACHMENT_TIMELINE_FALLBACK_FAILED", "message": str(exc)},
        ) from exc


@router.delete("/content/{kind}/{content_id}/attachments/{attachment_id}", dependencies=[Depends(require_session)])
def delete_content_attachment(
    kind: Literal["event", "memory", "plan"],
    content_id: str,
    attachment_id: str,
    vault: Annotated[VaultManager, Depends(get_vault)],
) -> dict:
    try:
        return envelope(
            vault.delete_attachment(
                kind=kind,
                content_id=content_id,
                attachment_id=attachment_id,
            )
        )
    except ContentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ATTACHMENT_NOT_FOUND", "message": str(exc)},
        ) from exc
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

