"""Strict Red-Green Negative Tests for Craw-assisted matching candidate quality.

Directly imports and tests the PRODUCTION FUNCTION:
    app.services.matching.craw_assisted_discovery.discover_craw_assisted_candidates

These assertions strictly require that:
- ONLY the true author is discovered.
- Co-authors sharing only surname ('Nguyen') or middle name ('Van', 'Thi') MUST be rejected as unattributed.
- On the current code (df0c4d3), these tests will FAIL (RED) because of the 1-token overlap flaw.
- After fixing craw_assisted_discovery.py, these tests will PASS (GREEN).
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

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


# ---------------------------------------------------------------------------
# CASE 1: TRÙNG HỌ (Shared surname only between Vietnamese co-authors)
# ---------------------------------------------------------------------------
def test_case_1_shared_surname_or_middle_name_must_not_anchor_unrelated_coauthors() -> None:
    """Case 1: Lecturer is Nguyễn Văn An.
    Paper has 3 authors:
      - Nguyễn Văn An (Author 1 - True author)
      - Nguyễn Thị Bình (Author 2 - shares surname 'Nguyễn', different person)
      - Trần Văn Cường (Author 3 - shares middle name 'Văn', different person)
    
    STRICT ASSERTION:
    Sharing ONLY 'Nguyễn' or ONLY 'Văn' with a co-author on the same paper
    must NOT cause Author 2 or Author 3 to be proposed as candidates.
    Only Author 1 can be in discovered; Author 2 and 3 must be in unattributed.
    """
    lecturer_id = uuid4()
    lecturer = _lecturer("Nguyễn Văn An", lecturer_id)
    snapshot = _snapshot(lecturer_id)
    publication = _publication("Research on AI", "10.1000/ai.2026")

    author1_id, author2_id, author3_id = uuid4(), uuid4(), uuid4()

    result = _run(
        existing_pairs=[],
        known=[_known(lecturer_id, snapshot.id, "Research on AI", "10.1000/ai.2026")],
        snapshots=[snapshot],
        publications=[publication],
        publication_authors=[
            _publication_author(publication.id, author1_id, author_order=1),
            _publication_author(publication.id, author2_id, author_order=2),
            _publication_author(publication.id, author3_id, author_order=3),
        ],
        scopus_authors=[
            _scopus_author(author1_id, "001", "Nguyen, Van An"),
            _scopus_author(author2_id, "002", "Nguyen, Thi Binh"),
            _scopus_author(author3_id, "003", "Tran, Van Cuong"),
        ],
        lecturers=[lecturer],
    )

    discovered_authors = {c.scopus_author_id for c in result.discovered}
    
    # Author 1 must be discovered
    assert author1_id in discovered_authors

    # STRICT CHECK: Neither Author 2 (Nguyen Thi Binh) nor Author 3 (Tran Van Cuong)
    # may be discovered for lecturer Nguyen Van An!
    # On current code, Author 3 has token 'van', matching lecturer 'van' -> FAILS (RED)!
    assert len(result.discovered) == 1, (
        f"RED on current code: Co-authors leaked into candidates: {[c.preferred_name for c in result.discovered]}"
    )
    assert result.discovered[0].scopus_author_id == author1_id
    assert {u.scopus_author_id for u in result.unattributed} == {author2_id, author3_id}


# ---------------------------------------------------------------------------
# CASE 2: TRÙNG TÊN ĐỆM (Shared middle name "Van" / "Thi")
# ---------------------------------------------------------------------------
def test_case_2_shared_middle_name_only_must_be_rejected() -> None:
    """Case 2: Lecturer is Lê Văn Phúc.
    Co-author on the paper is Phạm Văn Dũng.
    They share only 'Văn', which is a ubiquitous middle name in Vietnam.
    STRICT ASSERTION: Phạm Văn Dũng must NOT become candidate for Lê Văn Phúc.
    """
    lecturer_id = uuid4()
    lecturer = _lecturer("Lê Văn Phúc", lecturer_id)
    snapshot = _snapshot(lecturer_id)
    publication = _publication("Cloud Computing", "10.1000/cloud.2026")

    true_author_id, coauthor_id = uuid4(), uuid4()

    result = _run(
        existing_pairs=[],
        known=[_known(lecturer_id, snapshot.id, "Cloud Computing", "10.1000/cloud.2026")],
        snapshots=[snapshot],
        publications=[publication],
        publication_authors=[
            _publication_author(publication.id, true_author_id, author_order=1),
            _publication_author(publication.id, coauthor_id, author_order=2),
        ],
        scopus_authors=[
            _scopus_author(true_author_id, "101", "Le, Van Phuc"),
            _scopus_author(coauthor_id, "102", "Pham, Van Dung"),
        ],
        lecturers=[lecturer],
    )

    # STRICT CHECK: Only true author Le Van Phuc can be discovered.
    # Pham Van Dung shares 'van' -> on current code, len(discovered) == 2 -> FAILS (RED)!
    assert len(result.discovered) == 1, (
        f"RED on current code: Co-author leaked: {[c.preferred_name for c in result.discovered]}"
    )
    assert result.discovered[0].scopus_author_id == true_author_id
    assert coauthor_id in {u.scopus_author_id for u in result.unattributed}


# ---------------------------------------------------------------------------
# CASE 3: TRÙNG TÊN CHÍNH, KHÁC HỌ
# ---------------------------------------------------------------------------
def test_case_3_same_given_name_different_surname_between_coauthors_rejected() -> None:
    """Case 3: Lecturer Nguyễn Văn Dũng vs Scopus Trần Văn Dũng on same paper.
    Different surname between co-authors on the same paper -> must not falsely map.
    """
    lecturer_id = uuid4()
    lecturer = _lecturer("Nguyễn Văn Dũng", lecturer_id)
    snapshot = _snapshot(lecturer_id)
    publication = _publication("Distributed Systems", "10.1000/ds.2026")

    true_author_id, other_author_id = uuid4(), uuid4()

    result = _run(
        existing_pairs=[],
        known=[_known(lecturer_id, snapshot.id, "Distributed Systems", "10.1000/ds.2026")],
        snapshots=[snapshot],
        publications=[publication],
        publication_authors=[
            _publication_author(publication.id, true_author_id, author_order=1),
            _publication_author(publication.id, other_author_id, author_order=2),
        ],
        scopus_authors=[
            _scopus_author(true_author_id, "201", "Nguyen, Van Dung"),
            _scopus_author(other_author_id, "202", "Tran, Van Dung"),
        ],
        lecturers=[lecturer],
    )

    assert len(result.discovered) == 1, (
        f"RED on current code: Tran Van Dung falsely mapped to Nguyen Van Dung: {[c.preferred_name for c in result.discovered]}"
    )
    assert result.discovered[0].scopus_author_id == true_author_id
    assert other_author_id in {u.scopus_author_id for u in result.unattributed}


# ---------------------------------------------------------------------------
# CASE 4: TÊN VIẾT TẮT (Initials & Variants)
# ---------------------------------------------------------------------------
def test_case_4_abbreviated_initials_anchored_via_name_variant() -> None:
    """Case 4: Lecturer Nguyễn Văn Bình vs Scopus author preferred name 'Nguyen, V.-B.'
    with full name variant 'Nguyen Van Binh'.
    Must correctly DISCOVER this candidate.
    """
    lecturer_id, author_id = uuid4(), uuid4()
    lecturer = _lecturer("Nguyễn Văn Bình", lecturer_id)
    snapshot = _snapshot(lecturer_id)
    publication = _publication("Data Mining", "10.1000/dm.2026")

    result = _run(
        existing_pairs=[],
        known=[_known(lecturer_id, snapshot.id, "Data Mining", "10.1000/dm.2026")],
        snapshots=[snapshot],
        publications=[publication],
        publication_authors=[_publication_author(publication.id, author_id)],
        scopus_authors=[_scopus_author(author_id, "301", "Nguyen, V.-B.")],
        variants=[_variant(author_id, "Nguyen Van Binh")],
        lecturers=[lecturer],
    )

    assert len(result.discovered) == 1
    assert result.discovered[0].scopus_author_id == author_id
    assert len(result.unattributed) == 0


# ---------------------------------------------------------------------------
# CASE 5: CHUẨN HÓA KHÔNG DẤU VÀ UNICODE N2
# ---------------------------------------------------------------------------
def test_case_5_unaccented_and_special_character_d_folding() -> None:
    """Case 5: Lecturer 'Đặng Thị Thảo' vs Scopus 'Dang, Thi Thao'.
    N2 folding converts 'Đ' -> 'd' and strips diacritics. Must DISCOVER.
    """
    lecturer_id, author_id = uuid4(), uuid4()
    lecturer = _lecturer("Đặng Thị Thảo", lecturer_id)
    snapshot = _snapshot(lecturer_id)
    publication = _publication("Machine Learning", "10.1000/ml.2026")

    result = _run(
        existing_pairs=[],
        known=[_known(lecturer_id, snapshot.id, "Machine Learning", "10.1000/ml.2026")],
        snapshots=[snapshot],
        publications=[publication],
        publication_authors=[_publication_author(publication.id, author_id)],
        scopus_authors=[_scopus_author(author_id, "401", "Dang, Thi Thao")],
        lecturers=[lecturer],
    )

    assert len(result.discovered) == 1
    assert result.discovered[0].scopus_author_id == author_id


# ---------------------------------------------------------------------------
# CASE 6: HAI GIẢNG VIÊN ICTU CÙNG CÔNG BỐ
# ---------------------------------------------------------------------------
def test_case_6_two_ictu_lecturers_on_same_publication_no_cross_attribution() -> None:
    """Case 6: Two ICTU lecturers co-author the same paper.
    Lecturer A should map to Author A, Lecturer B to Author B.
    Cross pairs (Lecturer A <-> Author B) and (Lecturer B <-> Author A) must be rejected.
    """
    lec_a_id, lec_b_id = uuid4(), uuid4()
    lec_a = _lecturer("Vũ Thị Hoa", lec_a_id)
    lec_b = _lecturer("Đỗ Văn Kiên", lec_b_id)
    snap_a, snap_b = _snapshot(lec_a_id), _snapshot(lec_b_id)
    pub = _publication("Co-authored Paper", "10.1000/coauth.2026")
    auth_a_id, auth_b_id = uuid4(), uuid4()

    result = _run(
        existing_pairs=[],
        known=[
            _known(lec_a_id, snap_a.id, "Co-authored Paper", "10.1000/coauth.2026"),
            _known(lec_b_id, snap_b.id, "Co-authored Paper", "10.1000/coauth.2026"),
        ],
        snapshots=[snap_a, snap_b],
        publications=[pub],
        publication_authors=[
            _publication_author(pub.id, auth_a_id, author_order=1),
            _publication_author(pub.id, auth_b_id, author_order=2),
        ],
        scopus_authors=[
            _scopus_author(auth_a_id, "501", "Vu, Thi Hoa"),
            _scopus_author(auth_b_id, "502", "Do, Van Kien"),
        ],
        lecturers=[lec_a, lec_b],
    )

    discovered_pairs = {(c.lecturer_id, c.scopus_author_id) for c in result.discovered}
    assert (lec_a_id, auth_a_id) in discovered_pairs
    assert (lec_b_id, auth_b_id) in discovered_pairs

    # Cross pairs must NOT be in discovered
    assert (lec_a_id, auth_b_id) not in discovered_pairs
    assert (lec_b_id, auth_a_id) not in discovered_pairs

    # Cross pairs must be in unattributed
    unattributed_pairs = {(u.lecturer_id, u.scopus_author_id) for u in result.unattributed}
    assert (lec_a_id, auth_b_id) in unattributed_pairs
    assert (lec_b_id, auth_a_id) in unattributed_pairs


# ---------------------------------------------------------------------------
# CASE 7: THIẾU TÁC GIẢ TƯƠNG ỨNG TRONG SCOPUS
# ---------------------------------------------------------------------------
def test_case_7_publication_reconciles_but_no_author_position_matches() -> None:
    """Case 7: DOI matches a Scopus paper, but the Scopus author list only has
    foreign/unrelated authors. Zero candidates should be invented.
    """
    lecturer_id = uuid4()
    lecturer = _lecturer("Hoàng Minh Tuấn", lecturer_id)
    snapshot = _snapshot(lecturer_id)
    pub = _publication("International Collaboration", "10.1000/intl.2026")
    foreign_author_id = uuid4()

    result = _run(
        existing_pairs=[],
        known=[_known(lecturer_id, snapshot.id, "International Collaboration", "10.1000/intl.2026")],
        snapshots=[snapshot],
        publications=[pub],
        publication_authors=[_publication_author(pub.id, foreign_author_id)],
        scopus_authors=[_scopus_author(foreign_author_id, "601", "Smith, John D.")],
        lecturers=[lecturer],
    )

    assert len(result.discovered) == 0
    assert len(result.unattributed) == 1
    assert result.unattributed[0].scopus_author_id == foreign_author_id


# ---------------------------------------------------------------------------
# CASE 8: TÍNH TẤT ĐỊNH (DETERMINISM & RE-RUN SAFETY)
# ---------------------------------------------------------------------------
def test_case_8_idempotency_and_sorting_stability() -> None:
    """Case 8: Running twice produces identical candidates in identical order."""
    lecturer_id, author_id = uuid4(), uuid4()
    lecturer = _lecturer("Bùi Quang Huy", lecturer_id)
    snapshot = _snapshot(lecturer_id)
    pub = _publication("Software Engineering", "10.1000/se.2026")

    inputs = (
        [],
        [_known(lecturer_id, snapshot.id, "Software Engineering", "10.1000/se.2026")],
        [snapshot],
        [pub],
        [_publication_author(pub.id, author_id)],
        [_scopus_author(author_id, "701", "Bui, Quang Huy")],
        [lecturer],
    )

    run1 = _run(*inputs)
    run2 = _run(*inputs)

    assert len(run1.discovered) == len(run2.discovered) == 1
    assert run1.discovered[0].lecturer_id == run2.discovered[0].lecturer_id
    assert run1.discovered[0].scopus_author_id == run2.discovered[0].scopus_author_id
    assert run1.unattributed == run2.unattributed
