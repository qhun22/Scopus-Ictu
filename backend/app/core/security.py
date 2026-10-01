"""Security module — M0 HIGH-RISK STUB.

Allowed in M0:
  - signatures / interfaces
  - TODO stubs

Prohibited in M0:
  - JWT implementation
  - password hashing
  - auth workflows
"""

from __future__ import annotations


# TODO(M1): define interface / abstract base for token handling.
class TokenService:
    """M0 stub. TODO(M1): implement token creation and validation."""

    def create_access_token(self, data: dict) -> str:
        raise NotImplementedError("Token creation not implemented in M0.")

    def verify_access_token(self, token: str) -> dict:
        raise NotImplementedError("Token verification not implemented in M0.")


# TODO(M1): define interface / abstract base for password hashing.
class PasswordHasher:
    """M0 stub. TODO(M1): implement password hash and verify."""

    def hash(self, plaintext: str) -> str:
        raise NotImplementedError("Password hashing not implemented in M0.")

    def verify(self, plaintext: str, hashed: str) -> bool:
        raise NotImplementedError("Password verification not implemented in M0.")


# TODO(M1): inject real implementations in a dependency container.
token_service = TokenService()
password_hasher = PasswordHasher()
