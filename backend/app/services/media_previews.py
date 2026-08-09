from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from app.security.crypto import decrypt_bytes, encrypt_bytes


MEDIA_PREVIEW_AAD_PREFIX = b"lifegraph:v1:media-preview:"
MAX_MEDIA_PREVIEW_BYTES = 512 * 1024
_ALLOWED_PREVIEW_MEDIA_TYPES = {"image/jpeg", "image/webp", "image/png"}


class MediaPreviewError(ValueError):
    pass


def media_preview_aad(attachment_id: str) -> bytes:
    return MEDIA_PREVIEW_AAD_PREFIX + attachment_id.encode("utf-8")


class MediaPreviewStore:
    """Small encrypted derivative previews for media cards.

    Preview blobs are intentionally separate from the original attachment/media
    ciphertext so cards never have to decrypt a multi-GB video just to show a
    thumbnail.  The preview is a derivative and can be regenerated later; v0.0.9.6
    will decide its final .lifevault backup policy together with the external media
    library.
    """

    _SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

    def __init__(self, root: Path) -> None:
        self.root = root

    @classmethod
    def _safe_id(cls, attachment_id: str) -> str:
        value = str(attachment_id or "").strip()
        if not cls._SAFE_ID.fullmatch(value):
            raise MediaPreviewError("资料预览标识无效")
        return value

    def path_for(self, attachment_id: str) -> Path:
        value = self._safe_id(attachment_id)
        return self.root / value[:2].lower() / f"{value}.lgpreview"

    @staticmethod
    def validate_payload(content: bytes, media_type: str | None) -> str:
        if not content:
            raise MediaPreviewError("视频封面为空")
        if len(content) > MAX_MEDIA_PREVIEW_BYTES:
            raise MediaPreviewError("视频封面不能超过 512 KB")
        clean_type = str(media_type or "").split(";", 1)[0].strip().lower()
        if clean_type not in _ALLOWED_PREVIEW_MEDIA_TYPES:
            raise MediaPreviewError("视频封面仅支持 JPEG、WebP 或 PNG")
        return clean_type

    def write(
        self,
        master_key: bytes,
        attachment_id: str,
        content: bytes,
        *,
        media_type: str | None,
    ) -> tuple[bytes, str, str]:
        clean_type = self.validate_payload(content, media_type)
        nonce, ciphertext = encrypt_bytes(
            master_key,
            content,
            aad=media_preview_aad(self._safe_id(attachment_id)),
        )
        path = self.path_for(attachment_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        try:
            with temp.open("wb") as stream:
                stream.write(ciphertext)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
        return nonce, hashlib.sha256(content).hexdigest(), clean_type

    def read(self, master_key: bytes, attachment_id: str, nonce: bytes) -> bytes:
        path = self.path_for(attachment_id)
        if not path.is_file():
            raise MediaPreviewError("视频封面文件不存在")
        try:
            return decrypt_bytes(
                master_key,
                nonce,
                path.read_bytes(),
                aad=media_preview_aad(self._safe_id(attachment_id)),
            )
        except Exception as exc:
            raise MediaPreviewError("视频封面无法解密") from exc

    def delete(self, attachment_id: str) -> None:
        path = self.path_for(attachment_id)
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass
