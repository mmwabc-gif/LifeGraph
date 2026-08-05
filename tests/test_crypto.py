import os

import pytest

from app.security.crypto import CryptoError, KdfParams, unwrap_master_key, wrap_master_key


def test_master_key_wrap_roundtrip() -> None:
    master_key = os.urandom(32)
    slot = wrap_master_key(
        master_key,
        "123456",
        aad=b"test-slot",
        params=KdfParams(time_cost=1, memory_cost=8192, parallelism=1),
    )
    assert unwrap_master_key(slot, "123456", aad=b"test-slot") == master_key


def test_wrong_secret_is_rejected() -> None:
    master_key = os.urandom(32)
    slot = wrap_master_key(
        master_key,
        "123456",
        aad=b"test-slot",
        params=KdfParams(time_cost=1, memory_cost=8192, parallelism=1),
    )
    with pytest.raises(CryptoError):
        unwrap_master_key(slot, "654321", aad=b"test-slot")
