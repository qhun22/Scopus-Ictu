"""Authentication schemas — M0 scaffold.

JWT logic is prohibited in M0. These are empty stubs.
"""

from __future__ import annotations

from pydantic import BaseModel


class TokenPayload(BaseModel):
    """M0 stub. TODO(M1): define JWT payload fields."""

    pass


class LoginRequest(BaseModel):
    """M0 stub. TODO(M1): email + password fields."""

    pass


class LoginResponse(BaseModel):
    """M0 stub. TODO(M1): access_token + token_type."""

    pass