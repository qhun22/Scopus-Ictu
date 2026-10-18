"""D-3 (PROMPT 09): evidence level of an approved link comes from evidence rows only."""

from __future__ import annotations

import pytest

from app.services.identity_evidence_basis import evidence_basis


@pytest.mark.parametrize(
    ("rows", "level", "verified"),
    [
        ([], "NO_RECORDED_EVIDENCE", False),
        ([("NAME_SIMILARITY", "SUPPORTS")], "NAME_ONLY", False),
        ([("NAME_SIMILARITY", "SUPPORTS"), ("DOI_EXACT", "SUPPORTS")], "PUBLICATION_SUPPORT", False),
        ([("PUBLICATION_OVERLAP", "SUPPORTS")], "PUBLICATION_SUPPORT", False),
        ([("COAUTHOR_CONFIRMED", "SUPPORTS")], "PUBLICATION_SUPPORT", False),
        ([("ORCID_EXACT", "SUPPORTS"), ("NAME_SIMILARITY", "SUPPORTS")], "IDENTIFIER_SUPPORT", True),
        # contradicting evidence blocks "independently verified" even with an identifier match
        ([("ORCID_EXACT", "SUPPORTS"), ("NAME_SIMILARITY", "CONTRADICTS")], "IDENTIFIER_SUPPORT", False),
        # contradicting rows never count towards a level
        ([("ORCID_EXACT", "CONTRADICTS")], "NO_RECORDED_EVIDENCE", False),
        # affiliation evidence and the unspecified APPROVED_ID never raise the level
        ([("AFFILIATION_MATCH", "SUPPORTS")], "NO_RECORDED_EVIDENCE", False),
        ([("APPROVED_ID", "SUPPORTS")], "NO_RECORDED_EVIDENCE", False),
        ([("APPROVED_ID", "SUPPORTS"), ("NAME_SIMILARITY", "SUPPORTS")], "NAME_ONLY", False),
    ],
)
def test_evidence_level(rows, level, verified) -> None:
    basis = evidence_basis(rows)
    assert basis["level"] == level
    assert basis["independently_verified"] is verified


def test_counts_and_types_are_reported() -> None:
    basis = evidence_basis([("DOI_EXACT", "SUPPORTS"), ("DOI_EXACT", "SUPPORTS"), ("NAME_SIMILARITY", "SUPPORTS"),
                            ("AFFILIATION_MATCH", "SUPPORTS"), ("ORCID_EXACT", "CONTRADICTS")])
    assert basis["supporting_evidence_types"] == ["AFFILIATION_MATCH", "DOI_EXACT", "NAME_SIMILARITY"]
    assert basis["contradicting_evidence_types"] == ["ORCID_EXACT"]
    assert (basis["publication_evidence_count"], basis["name_evidence_count"],
            basis["affiliation_evidence_count"], basis["identifier_evidence_count"]) == (2, 1, 1, 0)
