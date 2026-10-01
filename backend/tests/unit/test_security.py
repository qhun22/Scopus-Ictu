"""Unit tests for password hashing and JWT token handling (M2.2)."""

from __future__ import annotations

import time
from app.core.security import PasswordHasher, TokenService


def test_password_hasher_basic() -> None:
    hasher = PasswordHasher()
    pwd = "MySecretPassword123!"

    hashed = hasher.hash(pwd)

    # 1. password hash != plaintext
    assert hashed != pwd
    assert "$argon2id$" in hashed

    # 2. correct password verify = true
    assert hasher.verify(pwd, hashed) is True

    # 3. wrong password verify = false
    assert hasher.verify("WrongPassword123!", hashed) is False
    assert hasher.verify("", hashed) is False
    assert hasher.verify(pwd, "invalid_hash_string") is False


def test_password_hasher_salt_randomness() -> None:
    hasher = PasswordHasher()
    pwd = "SamePassword123!"
    hash1 = hasher.hash(pwd)
    hash2 = hasher.hash(pwd)

    # Each hash must produce a different salt
    assert hash1 != hash2
    assert hasher.verify(pwd, hash1) is True
    assert hasher.verify(pwd, hash2) is True


def test_token_service_encode_decode() -> None:
    service = TokenService(secret_key="test-secret-key-123", expire_minutes=10)
    data = {"sub": "user-uuid-123", "email": "test@gmail.com", "role": "ADMIN"}

    token = service.create_access_token(data)
    assert isinstance(token, str)
    assert len(token) > 20

    payload = service.verify_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-uuid-123"
    assert payload["email"] == "test@gmail.com"
    assert payload["role"] == "ADMIN"
    assert "exp" in payload
    assert "iat" in payload


def test_token_service_invalid_or_expired() -> None:
    service = TokenService(secret_key="test-secret-key-123", expire_minutes=-5)
    data = {"sub": "user-uuid-123", "email": "test@gmail.com", "role": "ADMIN"}

    expired_token = service.create_access_token(data)
    # Expired token verification returns None
    assert service.verify_access_token(expired_token) is None

    # Tampered token verification returns None
    assert service.verify_access_token("invalid.token.structure") is None

    # Wrong secret key returns None
    other_service = TokenService(secret_key="different-secret-key", expire_minutes=10)
    valid_token = service.create_access_token(data)
    assert other_service.verify_access_token(valid_token) is None
