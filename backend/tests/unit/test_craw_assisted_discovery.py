"""Tests for Craw-assisted candidate discovery (see module docstring in
``app/services/matching/craw_assisted_discovery.py`` for why this exists and
why author position ALONE is not a sufficient identity anchor — the
enricher only adds evidence to candidates the name step already found, and
turning every author position on a reconciled publication into a candidate
would invent identity claims the data cannot support).
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from app.services.matching.craw_assisted_discovery import (
    discover_craw_assisted_candidates,
)


def _lecturer(full_name: str, lecturer_id: UUID | None = None):
    return SimpleNamespace(id=lecturer_id or uuid4(), full_name=full_name)


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


def _publication_author(publication_id: UUID, author_id: UUID, author_order: int = 1):
    return SimpleNamespace(
        id=uuid4(),
        publication_id=publication_id,
        scopus_author_id=author_id,
        author_order=author_order,
    )


def _scopus_author(author_id: UUID, scopus_id: str, preferred_name: str):
    return SimpleNamespace(id=author_id, scopus_id=scopus_id, preferred_name=preferred_name)


def _variant(author_id: UUID, variant_name: str, variant_type: str = "AUTHOR_FULL_NAME"):
    return SimpleNamespace(
        scopus_author_id=author_id, variant_name=variant_name, variant_type=variant_type
    )


def _run(
    existing_pairs,
    known,
    snapshots,
    publications,
    publication_authors,
    scopus_authors,
    lecturers,
    variants=(),
):
    return discover_craw_assisted_candidates(
        existing_pairs,
        known,
        snapshots,
        publications,
        publication_authors,
        scopus_authors,
        variants,
        lecturers,
    )


def test_doi_exact_known_publication_with_matching_name_discovers_candidate() -> None:
    lecturer_id, author_id = uuid4(), uuid4()
    lecturer = _lecturer("Nguyen Van An", lecturer_id)
    snapshot = _snapshot(lecturer_id)
    publication = _publication("exact title", "10.1000/exact")
    result = _run(
        existing_pairs=[],
        known=[_known(lecturer_id, snapshot.id, "different title", "10.1000/exact")],
        snapshots=[snapshot],
        publications=[publication],
        publication_authors=[_publication_author(publication.id, author_id)],
        scopus_authors=[_scopus_author(author_id, "100", "Nguyen Van An")],
        lecturers=[lecturer],
    )

    assert len(result.discovered) == 1
    discovered = result.discovered[0]
    assert discovered.lecturer_id == lecturer_id
    assert discovered.scopus_author_id == author_id
    assert discovered.evidence == ()
    assert len(discovered.publication_evidence) == 1
    assert discovered.publication_evidence[0].rule_id == "RULE_KNOWN_PUBLICATION_DOI_EXACT"
    assert result.conflicts == ()
    assert result.unattributed == ()


def test_five_author_publication_only_the_one_name_matching_author_becomes_a_candidate() -> None:
    """The core negative case the user called out: a paper with several
    authors must not turn into several candidates just because one
    lecturer's known-publication reconciles to it."""
    lecturer_id = uuid4()
    lecturer = _lecturer("Tran Thi Mai", lecturer_id)
    snapshot = _snapshot(lecturer_id)
    publication = _publication("multi author paper", "10.1000/multi")

    matching_author = uuid4()
    unrelated_authors = [uuid4() for _ in range(4)]
    unrelated_names = ["John Smith", "Maria Garcia", "Wei Zhang", "Alex Johnson"]

    result = _run(
        existing_pairs=[],
        known=[_known(lecturer_id, snapshot.id, "multi author paper", "10.1000/multi")],
        snapshots=[snapshot],
        publications=[publication],
        publication_authors=[
            _publication_author(publication.id, matching_author, author_order=1),
            *[
                _publication_author(publication.id, author_id, author_order=idx + 2)
                for idx, author_id in enumerate(unrelated_authors)
            ],
        ],
        scopus_authors=[
            _scopus_author(matching_author, "100", "Tran Thi Mai"),
            *[
                _scopus_author(author_id, str(200 + idx), name)
                for idx, (author_id, name) in enumerate(zip(unrelated_authors, unrelated_names))
            ],
        ],
        lecturers=[lecturer],
    )

    assert len(result.discovered) == 1
    assert result.discovered[0].scopus_author_id == matching_author
    # The 4 unrelated author positions are visible as evidence of a real
    # publication link, but never promoted to a candidate.
    assert len(result.unattributed) == 4
    assert {item.scopus_author_id for item in result.unattributed} == set(unrelated_authors)


def test_doi_match_but_wrong_author_position_is_not_attributed() -> None:
    """Same DOI, but the Scopus author on that position is a different
    person entirely — must not become a candidate."""
    lecturer_id, wrong_author = uuid4(), uuid4()
    lecturer = _lecturer("Pham Thi Lan", lecturer_id)
    snapshot = _snapshot(lecturer_id)
    publication = _publication("shared doi", "10.1000/shared")

    result = _run(
        existing_pairs=[],
        known=[_known(lecturer_id, snapshot.id, "shared doi", "10.1000/shared")],
        snapshots=[snapshot],
        publications=[publication],
        publication_authors=[_publication_author(publication.id, wrong_author)],
        scopus_authors=[_scopus_author(wrong_author, "999", "Hoang Minh Duc")],
        lecturers=[lecturer],
    )

    assert result.discovered == ()
    assert len(result.unattributed) == 1
    assert result.unattributed[0].scopus_author_id == wrong_author


def test_identical_name_is_attributed() -> None:
    lecturer_id, author_id = uuid4(), uuid4()
    lecturer = _lecturer("Le Van Hung", lecturer_id)
    snapshot = _snapshot(lecturer_id)
    publication = _publication("identical name case", "10.1000/identical")

    result = _run(
        existing_pairs=[],
        known=[_known(lecturer_id, snapshot.id, "identical name case", "10.1000/identical")],
        snapshots=[snapshot],
        publications=[publication],
        publication_authors=[_publication_author(publication.id, author_id)],
        scopus_authors=[_scopus_author(author_id, "100", "Le Van Hung")],
        lecturers=[lecturer],
    )

    assert len(result.discovered) == 1
    assert result.unattributed == ()


def test_abbreviated_name_variant_still_shares_a_surname_token_and_is_attributed() -> None:
    """Abbreviation case: Scopus surface is 'Nguyen V.' (initials), but a
    full-name variant on the same author shares the 'nguyen' token with the
    lecturer's full name, so the weak overlap check still anchors it."""
    lecturer_id, author_id = uuid4(), uuid4()
    lecturer = _lecturer("Nguyen Van Binh", lecturer_id)
    snapshot = _snapshot(lecturer_id)
    publication = _publication("abbreviation case", "10.1000/abbrev")

    result = _run(
        existing_pairs=[],
        known=[_known(lecturer_id, snapshot.id, "abbreviation case", "10.1000/abbrev")],
        snapshots=[snapshot],
        publications=[publication],
        publication_authors=[_publication_author(publication.id, author_id)],
        scopus_authors=[_scopus_author(author_id, "100", "Nguyen V.B.")],
        lecturers=[lecturer],
        variants=[_variant(author_id, "Nguyen Van Binh")],
    )

    assert len(result.discovered) == 1
    assert result.unattributed == ()


def test_two_ictu_lecturers_on_the_same_publication_both_attributed_independently() -> None:
    first_lecturer_id, second_lecturer_id = uuid4(), uuid4()
    first_lecturer = _lecturer("Vo Thi Hoa", first_lecturer_id)
    second_lecturer = _lecturer("Dang Van Kien", second_lecturer_id)
    first_snapshot = _snapshot(first_lecturer_id)
    second_snapshot = _snapshot(second_lecturer_id)
    publication = _publication("two ictu authors", "10.1000/two-ictu")
    first_author, second_author = uuid4(), uuid4()

    result = _run(
        existing_pairs=[],
        known=[
            _known(first_lecturer_id, first_snapshot.id, "two ictu authors", "10.1000/two-ictu"),
            _known(second_lecturer_id, second_snapshot.id, "two ictu authors", "10.1000/two-ictu"),
        ],
        snapshots=[first_snapshot, second_snapshot],
        publications=[publication],
        publication_authors=[
            _publication_author(publication.id, first_author, author_order=1),
            _publication_author(publication.id, second_author, author_order=2),
        ],
        scopus_authors=[
            _scopus_author(first_author, "100", "Vo Thi Hoa"),
            _scopus_author(second_author, "200", "Dang Van Kien"),
        ],
        lecturers=[first_lecturer, second_lecturer],
    )

    discovered_pairs = {(item.lecturer_id, item.scopus_author_id) for item in result.discovered}
    assert discovered_pairs == {
        (first_lecturer_id, first_author),
        (second_lecturer_id, second_author),
    }
    # Each lecturer's own known-publication is also checked against the
    # OTHER author position on the same paper; with no name overlap there,
    # those pairs are correctly reported as unattributed, not discovered.
    unattributed_pairs = {(item.lecturer_id, item.scopus_author_id) for item in result.unattributed}
    assert unattributed_pairs == {
        (first_lecturer_id, second_author),
        (second_lecturer_id, first_author),
    }


def test_pair_already_proposed_by_name_step_is_never_rediscovered() -> None:
    lecturer_id, author_id = uuid4(), uuid4()
    lecturer = _lecturer("Shared Name", lecturer_id)
    snapshot = _snapshot(lecturer_id)
    publication = _publication("shared", "10.1000/shared")
    result = _run(
        existing_pairs=[(lecturer_id, author_id)],
        known=[_known(lecturer_id, snapshot.id, "shared", "10.1000/shared")],
        snapshots=[snapshot],
        publications=[publication],
        publication_authors=[_publication_author(publication.id, author_id)],
        scopus_authors=[_scopus_author(author_id, "100", "Shared Name")],
        lecturers=[lecturer],
    )

    assert result.discovered == ()
    assert result.unattributed == ()


def test_ambiguous_title_reconciliation_discovers_nothing() -> None:
    lecturer_id, author_id = uuid4(), uuid4()
    lecturer = _lecturer("Ambiguous Person", lecturer_id)
    snapshot = _snapshot(lecturer_id)
    first = _publication("ambiguous title", eid="eid-1")
    second = _publication("ambiguous title", eid="eid-2")
    result = _run(
        existing_pairs=[],
        known=[_known(lecturer_id, snapshot.id, "ambiguous title")],
        snapshots=[snapshot],
        publications=[first, second],
        publication_authors=[
            _publication_author(first.id, author_id),
            _publication_author(second.id, author_id),
        ],
        scopus_authors=[_scopus_author(author_id, "100", "Ambiguous Person")],
        lecturers=[lecturer],
    )

    assert result.discovered == ()
    assert result.unattributed == ()
    assert len(result.conflicts) == 1
    assert result.conflicts[0].reason == "TITLE_AMBIGUOUS"


def test_snapshot_lecturer_mismatch_discovers_nothing() -> None:
    lecturer_id, other_lecturer, author_id = uuid4(), uuid4(), uuid4()
    lecturer = _lecturer("Mismatch Person", lecturer_id)
    snapshot = _snapshot(other_lecturer)
    publication = _publication("mismatch", "10.1000/mismatch")
    result = _run(
        existing_pairs=[],
        known=[_known(lecturer_id, snapshot.id, "mismatch", "10.1000/mismatch")],
        snapshots=[snapshot],
        publications=[publication],
        publication_authors=[_publication_author(publication.id, author_id)],
        scopus_authors=[_scopus_author(author_id, "100", "Mismatch Person")],
        lecturers=[lecturer],
    )

    assert result.discovered == ()
    assert result.conflicts[0].reason == "SNAPSHOT_LECTURER_MISMATCH"


def test_publication_with_no_author_rows_discovers_nothing() -> None:
    lecturer_id = uuid4()
    lecturer = _lecturer("Orphan Person", lecturer_id)
    snapshot = _snapshot(lecturer_id)
    publication = _publication("orphan", "10.1000/orphan")
    result = _run(
        existing_pairs=[],
        known=[_known(lecturer_id, snapshot.id, "orphan", "10.1000/orphan")],
        snapshots=[snapshot],
        publications=[publication],
        publication_authors=[],
        scopus_authors=[],
        lecturers=[lecturer],
    )

    assert result.discovered == ()
    assert result.unattributed == ()


def test_rerun_is_deterministic() -> None:
    lecturer_id, author_id = uuid4(), uuid4()
    lecturer = _lecturer("Stable Person", lecturer_id)
    snapshot = _snapshot(lecturer_id)
    publication = _publication("stable", "10.1000/stable")
    inputs = (
        [],
        [_known(lecturer_id, snapshot.id, "stable", "10.1000/stable")],
        [snapshot],
        [publication],
        [_publication_author(publication.id, author_id)],
        [_scopus_author(author_id, "100", "Stable Person")],
        [lecturer],
    )

    first = _run(*inputs)
    second = _run(*inputs)

    assert first.discovered == second.discovered
    assert first.unattributed == second.unattributed


def test_doi_discovery_does_not_mutate_name_step_candidates() -> None:
    """Purely additive: an existing pair's own evidence is untouched because
    this module never even receives or returns the name-step candidates —
    it only returns the newly discovered ones."""
    lecturer_id, existing_author, new_author = uuid4(), uuid4(), uuid4()
    lecturer = _lecturer("Combo Person", lecturer_id)
    snapshot = _snapshot(lecturer_id)
    publication = _publication("combo", "10.1000/combo")
    result = _run(
        existing_pairs=[(lecturer_id, existing_author)],
        known=[_known(lecturer_id, snapshot.id, "combo", "10.1000/combo")],
        snapshots=[snapshot],
        publications=[publication],
        publication_authors=[
            _publication_author(publication.id, existing_author, author_order=1),
            _publication_author(publication.id, new_author, author_order=2),
        ],
        scopus_authors=[
            _scopus_author(existing_author, "100", "Combo Person"),
            _scopus_author(new_author, "200", "Combo Person"),
        ],
        lecturers=[lecturer],
    )

    assert len(result.discovered) == 1
    assert result.discovered[0].scopus_author_id == new_author
