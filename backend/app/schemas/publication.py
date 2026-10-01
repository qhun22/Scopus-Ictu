"""Publication schemas — M0 scaffold."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.schemas.common import TimestampMixin


class PublicationBase(BaseModel):
    """M0 stub. TODO(M1): eid, doi, title, year, journal, etc."""

    pass


class PublicationCreate(PublicationBase):
    """M0 stub."""

    pass


class PublicationResponse(PublicationBase, TimestampMixin):
    """M0 stub."""

    model_config = ConfigDict(from_attributes=True)

    id: int


class ScopusAuthorBase(BaseModel):
    """M0 stub. TODO(M1): scopus_author_id, name, orcid, etc."""

    pass


class ScopusAuthorCreate(ScopusAuthorBase):
    """M0 stub."""

    pass


class ScopusAuthorResponse(ScopusAuthorBase):
    """M0 stub."""

    model_config = ConfigDict(from_attributes=True)

    id: int


class PublicationAuthorResponse(BaseModel):
    """M0 stub."""

    model_config = ConfigDict(from_attributes=True)

    id: int