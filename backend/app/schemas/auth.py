"""Authentication Pydantic schemas — M2.2 contract.

Defines input payloads for login requests, and public safe user response models
that strictly omit sensitive fields such as password_hash.
"""

from __future__ import annotations

import uuid
from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Payload for user login."""

    email: str = Field(..., description="Email address of the user")
    password: str = Field(..., description="Plaintext password submitted by user")


class UserResponse(BaseModel):
    """Public authenticated user profile representation."""

    id: uuid.UUID
    email: str
    display_name: str
    role: str
    lecturer_id: uuid.UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class TokenPayload(BaseModel):
    """Internal JWT decoded claims."""

    sub: str
    email: str
    role: str
    exp: int
    iat: int | None = None


class MessageResponse(BaseModel):
    """Generic status/message response."""

    message: str