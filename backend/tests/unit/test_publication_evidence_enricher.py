"""M2.7A-5 focused tests for transient publication-evidence enrichment."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from app.services.matching.candidate_types import LecturerScopusCandidate
from app.services.matching.publication_evidence_enricher import (
    enrich_candidates,
    normalize_doi_for_matching,
)


def _candidate(lecturer_id: UUID, author_id: UUID, scopus_id: str) -> LecturerScopusCandidate:
    return LecturerScopusCandidate(
        lecturer_id=lecturer_id,
        scopus_author_id=author_id,
        scopus_id=scopus_id,
        preferred_name=f"Author {scopus_id}",
        evidence=(),
    )


def _snapshot(lecturer_id: UUID, snapshot_id: UUID | None = None):
    return SimpleNamespace(id=snapshot_id or uuid4(), lecturer_id=lecturer_id)


def _known(
    lecturer_id: UUID,
    snapshot_id: UUID,
    title: str,
    doi: str | None = None,
    known_id: UUID | None = None,
):
    return SimpleNamespace(
        id=known_id or uuid4(),
        lecturer_id=lecturer_id,
        snapshot_id=snapshot_id,
        title_normalized=title,
        doi_normalized=doi,
    )


def _publication(
    title: str,
    doi: str | None = None,
    eid: str = "2-s2.0-1",
    publication_id: UUID | None = None,
):
    return SimpleNamespace(
        id=publication_id or uuid4(),
        eid=eid,
        doi=doi,
        title=f"Canonical {title}",
        title_normalized=title,
    )


def _publication_author(publication_id: UUID, author_id: UUID):
    return SimpleNamespace(publication_id=publication_id, scopus_author_id=author_id)


def _run(candidates, known, snapshots, publications, publication_authors):
    return enrich_candidates(
        candidates,
        known,
        snapshots,
        publications,
        publication_authors,
    )


def test_doi_exact_reconciliation_emits_explainable_evidence() -> None:
    lecturer_id, author_id = uuid4(), uuid4()
    snapshot = _snapshot(lecturer_id)
    publication = _publication("exact title", "10.1000/exact")
    result = _run(
        [_candidate(lecturer_id, author_id, "100")],
        [_known(lecturer_id, snapshot.id, "different title", "10.1000/exact")],
        [snapshot],
        [publication],
        [_publication_author(publication.id, author_id)],
    )

    evidence = result[0].publication_evidence
    assert len(evidence) == 1
    assert evidence[0].rule_id == "RULE_KNOWN_PUBLICATION_DOI_EXACT"
    assert evidence[0].reconciliation == "DOI_EXACT"
    assert evidence[0].canonical_publication_id == publication.id
    assert evidence[0].candidate_scopus_author_id == author_id
    assert result.conflicts == ()


def test_doi_mismatch_uses_exact_title_fallback() -> None:
    lecturer_id, author_id = uuid4(), uuid4()
    snapshot = _snapshot(lecturer_id)
    publication = _publication("same title", "10.1000/canonical")
    result = _run(
        [_candidate(lecturer_id, author_id, "100")],
        [_known(lecturer_id, snapshot.id, "same title", "10.1000/other")],
        [snapshot],
        [publication],
        [_publication_author(publication.id, author_id)],
    )

    assert result[0].publication_evidence[0].rule_id == "RULE_KNOWN_PUBLICATION_TITLE_EXACT"
    assert result[0].publication_evidence[0].reconciliation == "TITLE_EXACT"


def test_doi_normalization_is_case_insensitive_but_does_not_repair_values() -> None:
    assert normalize_doi_for_matching(" DOI: 10.1000/AbC ") == "10.1000/abc"
    assert normalize_doi_for_matching("http://dx.doi.org/10.1000/AbC") == "10.1000/abc"
    assert normalize_doi_for_matching("10.1000/ab c") == "10.1000/ab c"


def test_doi_precedence_does_not_add_title_evidence_for_same_publication() -> None:
    lecturer_id, author_id = uuid4(), uuid4()
    snapshot = _snapshot(lecturer_id)
    publication = _publication("same title", "10.1000/exact")
    result = _run(
        [_candidate(lecturer_id, author_id, "100")],
        [_known(lecturer_id, snapshot.id, "same title", "10.1000/exact")],
        [snapshot],
        [publication],
        [_publication_author(publication.id, author_id)],
    )

    assert len(result[0].publication_evidence) == 1
    assert result[0].publication_evidence[0].reconciliation == "DOI_EXACT"


def test_doi_and_unique_title_pointing_to_different_publications_fail_closed() -> None:
    lecturer_id, author_id = uuid4(), uuid4()
    snapshot = _snapshot(lecturer_id)
    doi_publication = _publication("doi title", "10.1000/exact", "eid-doi")
    title_publication = _publication("title match", "10.1000/other", "eid-title")
    result = _run(
        [_candidate(lecturer_id, author_id, "100")],
        [_known(lecturer_id, snapshot.id, "title match", "10.1000/exact")],
        [snapshot],
        [doi_publication, title_publication],
        [
            _publication_author(doi_publication.id, author_id),
            _publication_author(title_publication.id, author_id),
        ],
    )

    assert result[0].publication_evidence == ()
    assert result.conflicts[0].reason == "DOI_TITLE_CONFLICT"


def test_ambiguous_title_is_not_support() -> None:
    lecturer_id, author_id = uuid4(), uuid4()
    snapshot = _snapshot(lecturer_id)
    first = _publication("ambiguous title", eid="eid-1")
    second = _publication("ambiguous title", eid="eid-2")
    result = _run(
        [_candidate(lecturer_id, author_id, "100")],
        [_known(lecturer_id, snapshot.id, "ambiguous title")],
        [snapshot],
        [first, second],
        [
            _publication_author(first.id, author_id),
            _publication_author(second.id, author_id),
        ],
    )

    assert result[0].publication_evidence == ()
    assert result.conflicts[0].reason == "TITLE_AMBIGUOUS"


def test_doi_match_with_ambiguous_title_fails_closed() -> None:
    lecturer_id, author_id = uuid4(), uuid4()
    snapshot = _snapshot(lecturer_id)
    first = _publication("ambiguous title", "10.1000/exact", eid="eid-1")
    second = _publication("ambiguous title", "10.1000/other", eid="eid-2")
    result = _run(
        [_candidate(lecturer_id, author_id, "100")],
        [_known(lecturer_id, snapshot.id, "ambiguous title", "10.1000/exact")],
        [snapshot],
        [first, second],
        [
            _publication_author(first.id, author_id),
            _publication_author(second.id, author_id),
        ],
    )

    assert result[0].publication_evidence == ()
    assert result.conflicts[0].reason == "TITLE_AMBIGUOUS"
    assert result.conflicts[0].doi_publication_ids == (first.id,)


def test_no_match_and_missing_publication_author_emit_no_evidence() -> None:
    lecturer_id, author_id = uuid4(), uuid4()
    snapshot = _snapshot(lecturer_id)
    publication = _publication("canonical", "10.1000/canonical")
    result = _run(
        [_candidate(lecturer_id, author_id, "100")],
        [_known(lecturer_id, snapshot.id, "unrelated", "10.1000/missing")],
        [snapshot],
        [publication],
        [],
    )

    assert result[0].publication_evidence == ()
    assert result.conflicts == ()


def test_existing_candidates_are_preserved_and_publication_authors_do_not_create_candidates() -> (
    None
):
    lecturer_id = uuid4()
    first_author, second_author, unseen_author = uuid4(), uuid4(), uuid4()
    snapshot = _snapshot(lecturer_id)
    publication = _publication("shared", "10.1000/shared")
    candidates = [
        _candidate(lecturer_id, first_author, "100"),
        _candidate(lecturer_id, second_author, "200"),
    ]
    result = _run(
        candidates,
        [_known(lecturer_id, snapshot.id, "shared", "10.1000/shared")],
        [snapshot],
        [publication],
        [
            _publication_author(publication.id, first_author),
            _publication_author(publication.id, unseen_author),
        ],
    )

    assert len(result) == 2
    assert [item.scopus_id for item in result] == ["100", "200"]
    assert len(result[0].publication_evidence) == 1
    assert result[1].publication_evidence == ()


def test_all_existing_candidates_on_one_publication_can_receive_evidence() -> None:
    lecturer_id = uuid4()
    first_author, second_author = uuid4(), uuid4()
    snapshot = _snapshot(lecturer_id)
    publication = _publication("shared", "10.1000/shared")
    result = _run(
        [
            _candidate(lecturer_id, first_author, "100"),
            _candidate(lecturer_id, second_author, "200"),
        ],
        [_known(lecturer_id, snapshot.id, "shared", "10.1000/shared")],
        [snapshot],
        [publication],
        [
            _publication_author(publication.id, first_author),
            _publication_author(publication.id, second_author),
        ],
    )

    assert [len(item.publication_evidence) for item in result] == [1, 1]


def test_duplicate_known_publication_provenance_deduplicates_by_canonical_publication() -> None:
    lecturer_id, author_id = uuid4(), uuid4()
    first_snapshot = _snapshot(lecturer_id)
    second_snapshot = _snapshot(lecturer_id)
    publication = _publication("same", "10.1000/same")
    first = _known(lecturer_id, first_snapshot.id, "same", None)
    second = _known(lecturer_id, second_snapshot.id, "same", "10.1000/same")
    result = _run(
        [_candidate(lecturer_id, author_id, "100")],
        [first, second],
        [first_snapshot, second_snapshot],
        [publication],
        [_publication_author(publication.id, author_id)],
    )

    assert len(result[0].publication_evidence) == 1
    assert result[0].publication_evidence[0].rule_id == "RULE_KNOWN_PUBLICATION_DOI_EXACT"
    assert result[0].publication_evidence[0].lecturer_snapshot_id == second_snapshot.id


def test_cross_lecturer_known_publication_cannot_support_other_lecturer_candidate() -> None:
    first_lecturer, second_lecturer, author_id = uuid4(), uuid4(), uuid4()
    snapshot = _snapshot(first_lecturer)
    publication = _publication("owned by first", "10.1000/owned")
    result = _run(
        [
            _candidate(first_lecturer, author_id, "100"),
            _candidate(second_lecturer, author_id, "100"),
        ],
        [_known(first_lecturer, snapshot.id, "owned by first", "10.1000/owned")],
        [snapshot],
        [publication],
        [_publication_author(publication.id, author_id)],
    )

    assert len(result[0].publication_evidence) == 1
    assert result[1].publication_evidence == ()


def test_two_ambiguous_candidates_for_same_lecturer_each_remain_unsupported() -> None:
    lecturer_id, first_author, second_author = uuid4(), uuid4(), uuid4()
    snapshot = _snapshot(lecturer_id)
    first = _publication("ambiguous", eid="eid-a")
    second = _publication("ambiguous", eid="eid-b")
    result = _run(
        [
            _candidate(lecturer_id, first_author, "100"),
            _candidate(lecturer_id, second_author, "200"),
        ],
        [_known(lecturer_id, snapshot.id, "ambiguous")],
        [snapshot],
        [first, second],
        [
            _publication_author(first.id, first_author),
            _publication_author(second.id, second_author),
        ],
    )

    assert [item.publication_evidence for item in result] == [(), ()]
    assert len(result.conflicts) == 1


def test_snapshot_lecturer_mismatch_is_fail_closed() -> None:
    lecturer_id, other_lecturer, author_id = uuid4(), uuid4(), uuid4()
    snapshot = _snapshot(other_lecturer)
    publication = _publication("mismatch", "10.1000/mismatch")
    result = _run(
        [_candidate(lecturer_id, author_id, "100")],
        [_known(lecturer_id, snapshot.id, "mismatch", "10.1000/mismatch")],
        [snapshot],
        [publication],
        [_publication_author(publication.id, author_id)],
    )

    assert result[0].publication_evidence == ()
    assert result.conflicts[0].reason == "SNAPSHOT_LECTURER_MISMATCH"


def test_enrichment_rerun_is_deterministic() -> None:
    lecturer_id, author_id = uuid4(), uuid4()
    snapshot = _snapshot(lecturer_id)
    publication = _publication("stable", "10.1000/stable")
    inputs = (
        [_candidate(lecturer_id, author_id, "100")],
        [_known(lecturer_id, snapshot.id, "stable", "10.1000/stable")],
        [snapshot],
        [publication],
        [_publication_author(publication.id, author_id)],
    )

    first = _run(*inputs)
    second = _run(*inputs)

    assert first == second
