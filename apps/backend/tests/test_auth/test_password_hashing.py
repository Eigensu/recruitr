"""Password hashing guarantees.

These pin the behaviour that broke signup in production: passlib 1.7.4 probes
for a historical bcrypt bug by hashing a >72-byte secret, which bcrypt 5.0
rejects outright, so every hash() and verify() call raised and signup 500'd.
"""

import pytest

from app.modules.auth.security import get_password_hash, verify_password

# Produced by the previous implementation (passlib 1.7.4 + bcrypt 4.0.1) so a
# regression that changes the hash scheme locks out every existing account.
LEGACY_HASH = "$2b$12$MiKiTOIBY71GTdoAfx1tEu0Os5viTZISjGQRZB.OrXBfF1rKnQR0i"
LEGACY_PASSWORD = "Password123!"

# Same, for a password over bcrypt's 72-byte limit — passlib stored only the
# truncated prefix, so these users must still be able to log in.
LEGACY_LONG_HASH = "$2b$12$v43so6fUAcMSaYmcvu.s0ukQgJdWXEc938QjONRNdh.go8QdPtGda"
LEGACY_LONG_PASSWORD = "a" * 100


def test_hash_then_verify_roundtrip() -> None:
    hashed = get_password_hash(LEGACY_PASSWORD)
    assert hashed.startswith("$2b$")
    assert verify_password(LEGACY_PASSWORD, hashed)


def test_wrong_password_is_rejected() -> None:
    assert not verify_password("wrong", get_password_hash(LEGACY_PASSWORD))


def test_hashes_are_salted() -> None:
    assert get_password_hash(LEGACY_PASSWORD) != get_password_hash(LEGACY_PASSWORD)


def test_existing_passlib_hashes_still_verify() -> None:
    assert verify_password(LEGACY_PASSWORD, LEGACY_HASH)
    assert not verify_password("wrong", LEGACY_HASH)


@pytest.mark.parametrize(
    "password",
    [
        "a" * 100,  # over the 72-byte limit — must not raise
        "🔐é" * 40,  # multibyte, well over 72 bytes once encoded
        "x" * 72,  # exactly at the limit
    ],
)
def test_long_passwords_do_not_raise(password: str) -> None:
    assert verify_password(password, get_password_hash(password))


def test_existing_truncated_passlib_hash_still_verifies() -> None:
    assert verify_password(LEGACY_LONG_PASSWORD, LEGACY_LONG_HASH)


def test_malformed_stored_hash_fails_closed() -> None:
    """A corrupt hash must be a failed login, never a 500 and never a pass."""
    for bad in ("", "not-a-hash", "$2b$broken"):
        assert not verify_password(LEGACY_PASSWORD, bad)
