from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Any

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CryptoError(ValueError):
    """Raised when encrypted data cannot be decrypted or validated."""


@dataclass(frozen=True, slots=True)
class KdfParams:
    time_cost: int = 3
    memory_cost: int = 65_536
    parallelism: int = 2
    hash_len: int = 32

    def to_dict(self) -> dict[str, int | str]:
        return {
            "name": "argon2id",
            "time_cost": self.time_cost,
            "memory_cost": self.memory_cost,
            "parallelism": self.parallelism,
            "hash_len": self.hash_len,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "KdfParams":
        if value.get("name") != "argon2id":
            raise CryptoError("不支持的密钥派生算法")
        return cls(
            time_cost=int(value["time_cost"]),
            memory_cost=int(value["memory_cost"]),
            parallelism=int(value["parallelism"]),
            hash_len=int(value["hash_len"]),
        )


def b64e(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def b64d(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value.encode("ascii"))
    except Exception as exc:  # pragma: no cover - defensive parsing
        raise CryptoError("加密元数据格式错误") from exc


def derive_key(secret: str, salt: bytes, params: KdfParams) -> bytes:
    if not secret:
        raise CryptoError("解锁凭据不能为空")
    return hash_secret_raw(
        secret=secret.encode("utf-8"),
        salt=salt,
        time_cost=params.time_cost,
        memory_cost=params.memory_cost,
        parallelism=params.parallelism,
        hash_len=params.hash_len,
        type=Type.ID,
    )


def wrap_master_key(master_key: bytes, secret: str, *, aad: bytes, params: KdfParams) -> dict[str, Any]:
    salt = os.urandom(16)
    wrapping_key = derive_key(secret, salt, params)
    nonce = os.urandom(12)
    ciphertext = AESGCM(wrapping_key).encrypt(nonce, master_key, aad)
    return {
        "salt": b64e(salt),
        "nonce": b64e(nonce),
        "ciphertext": b64e(ciphertext),
        "kdf": params.to_dict(),
    }


def unwrap_master_key(slot: dict[str, Any], secret: str, *, aad: bytes) -> bytes:
    params = KdfParams.from_dict(slot["kdf"])
    wrapping_key = derive_key(secret, b64d(slot["salt"]), params)
    try:
        return AESGCM(wrapping_key).decrypt(
            b64d(slot["nonce"]), b64d(slot["ciphertext"]), aad
        )
    except InvalidTag as exc:
        raise CryptoError("PIN 或恢复凭据不正确") from exc


def encrypt_bytes(master_key: bytes, plaintext: bytes, *, aad: bytes) -> tuple[bytes, bytes]:
    nonce = os.urandom(12)
    return nonce, AESGCM(master_key).encrypt(nonce, plaintext, aad)


def decrypt_bytes(master_key: bytes, nonce: bytes, ciphertext: bytes, *, aad: bytes) -> bytes:
    try:
        return AESGCM(master_key).decrypt(nonce, ciphertext, aad)
    except InvalidTag as exc:
        raise CryptoError("加密数据完整性验证失败") from exc


def encrypt_json(master_key: bytes, value: dict[str, Any], *, aad: bytes) -> tuple[bytes, bytes]:
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return encrypt_bytes(master_key, raw, aad=aad)


def decrypt_json(master_key: bytes, nonce: bytes, ciphertext: bytes, *, aad: bytes) -> dict[str, Any]:
    raw = decrypt_bytes(master_key, nonce, ciphertext, aad=aad)
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise CryptoError("加密数据结构错误")
    return value
