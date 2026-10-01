"""Security module — M2.2 Argon2id password hashing and JWT token handling.

Provides cryptographic primitives for user authentication, password verification,
and stateless signed session token creation/verification.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings

_ph = Argon2Hasher()


class PasswordHasher:
    """Argon2id password hasher and constant-time verifier."""

    def hash(self, plaintext: str) -> str:
        """Hash a plaintext password using Argon2id with random salt."""
        return _ph.hash(plaintext)

    def verify(self, plaintext: str, hashed: str) -> bool:
        """Verify plaintext password against an Argon2id hash.
        
        Returns True if matched, False otherwise. Never raises on invalid hashes.
        """
        try:
            return _ph.verify(hashed, plaintext)
        except (VerifyMismatchError, VerificationError, InvalidHashError, Exception):
            return False


class TokenService:
    """JWT Token management service using HMAC SHA-256."""

    def __init__(
        self,
        secret_key: str | None = None,
        algorithm: str = "HS256",
        expire_minutes: int | None = None,
    ) -> None:
        self.secret_key = secret_key or settings.secret_key
        self.algorithm = algorithm
        self.expire_minutes = expire_minutes or settings.access_token_expire_minutes

    def create_access_token(
        self,
        data: dict[str, Any],
        expires_delta: timedelta | None = None,
    ) -> str:
        """Encode given payload dictionary into a signed JWT string."""
        to_encode = data.copy()
        now = datetime.now(timezone.utc)
        if expires_delta is not None:
            expire = now + expires_delta
        else:
            expire = now + timedelta(minutes=self.expire_minutes)

        to_encode.update({
            "exp": int(expire.timestamp()),
            "iat": int(now.timestamp()),
        })
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def verify_access_token(self, token: str) -> dict[str, Any] | None:
        """Verify JWT signature and expiration, returning the payload if valid."""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
            )
            return payload
        except (jwt.PyJWTError, Exception):
            return None


token_service = TokenService()
password_hasher = PasswordHasher()

__all__ = ["PasswordHasher", "TokenService", "password_hasher", "token_service"]
