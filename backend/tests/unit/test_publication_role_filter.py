"""Publication detail: internal data, incl. the override note, is withheld from non-ADMIN."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1.endpoints.publications import _for_role
from app.schemas.publication_api import (
    AffiliationOverrideRead,
    PublicationAuthorRead,
    PublicationDetailResponse,
)

INTERNAL_NOTE = "internal note naming a person"


def make_detail() -> PublicationDetailResponse:
    override = AffiliationOverrideRead.model_construct(
        affiliation_text="Example University",
        confidence="CORROBORATED",
        evidence_url="https://example.invalid/evidence",
        reason=INTERNAL_NOTE,
        note="Entered by an ADMIN after manual review.",
    )
    author = PublicationAuthorRead.model_construct(
        author_order=1, scopus_id="57000000001", preferred_name="Example, A.",
        affiliation_overrides=[override],
    )
    return PublicationDetailResponse.model_construct(
        eid="2-s2.0-00000001", authors=[author],
        provenance=["file.csv:row 3"], approved_lecturer_links=["a lecturer link"],
    )


def reader(role: str):
    return SimpleNamespace(role=role)


@pytest.mark.parametrize("who", [None, reader("LECTURER"), reader("REVIEWER")])
def test_non_admin_never_sees_the_internal_override_note(who) -> None:
    view = _for_role(make_detail(), who)

    override = view.authors[0].affiliation_overrides[0]
    assert override.reason == ""
    assert override.affiliation_text == "Example University"
    assert override.confidence == "CORROBORATED"
    assert override.evidence_url == "https://example.invalid/evidence"
    assert view.provenance == [] and view.approved_lecturer_links == []


def test_admin_keeps_everything() -> None:
    detail = make_detail()

    view = _for_role(detail, reader("ADMIN"))

    assert view.authors[0].affiliation_overrides[0].reason == INTERNAL_NOTE
    assert view.provenance and view.approved_lecturer_links


def test_filtering_does_not_change_the_original_object() -> None:
    detail = make_detail()

    _for_role(detail, None)

    assert detail.authors[0].affiliation_overrides[0].reason == INTERNAL_NOTE
