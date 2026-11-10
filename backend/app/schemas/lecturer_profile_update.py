"""Allowlisted lecturer self-service fields; identity/account keys are forbidden."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LecturerProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    academic_rank: str | None = Field(default=None, max_length=50)
    academic_degree: str | None = Field(default=None, max_length=50)
    position: str | None = Field(default=None, max_length=100)
    specialization: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    gender: Literal["Nam", "Nữ", "Khác"] | None = None
    date_of_birth: date | None = None
    orcid: str | None = Field(default=None, max_length=100)
    repository_profile_url: str | None = Field(default=None, max_length=2048)

    @field_validator(
        "academic_rank",
        "academic_degree",
        "position",
        "specialization",
        "phone",
        "gender",
        "orcid",
        "repository_profile_url",
        "date_of_birth",
        mode="before",
    )
    @classmethod
    def clean_text(cls, value):
        if not isinstance(value, str):
            return value
        value = value.strip()
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("Control characters are not allowed")
        return value or None
