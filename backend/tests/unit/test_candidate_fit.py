"""Degree-of-fit labels: deterministic, explainable, never a decision."""

from __future__ import annotations

import pytest

from app.services.candidate_fit import assess_fit, is_ictu_affiliation


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Trường Đại Học Công Nghệ Thông Tin Và Truyền Thông", True),
        ("Trường Đại học Công nghệ thông tin & Truyền thông, Thái Nguyên", True),
        ("Faculty of IT, University of Information and Communication Technology (ICTU), Thai Nguyen", True),
        ("University of Information and Communication Technology, Thai Nguyen, Vietnam", True),
        ("ICTU", True),
        ("Kyonggi University, Suwon, South Korea", False),
        ("Hanoi University of Information and Communication Technology", False),   # no Thai Nguyen
        ("Test", False),
        ("", False),
        (None, False),
    ],
)
def test_ictu_affiliation_detection(text, expected):
    assert is_ictu_affiliation(text) is expected


def _fit(**overrides):
    base = {
        "name_evidence_count": 0,
        "publication_support_count": 0,
        "ictu_affiliation_papers": 0,
        "is_shared_author": False,
        "is_ambiguous_lecturer": False,
    }
    base.update(overrides)
    return assess_fit(**base)


def test_high_needs_publication_support_and_ictu_affiliation_and_an_unshared_id():
    result = _fit(name_evidence_count=2, publication_support_count=1, ictu_affiliation_papers=3)
    assert result.level == "HIGH"
    assert {"PUBLICATION_SUPPORT", "ICTU_AFFILIATION", "NAME_MATCH"} <= set(result.reasons)
    assert result.ictu_affiliation_papers == 3


def test_a_shared_id_never_rises_above_medium():
    result = _fit(name_evidence_count=2, publication_support_count=2, ictu_affiliation_papers=2,
                  is_shared_author=True)
    assert result.level == "MEDIUM"
    assert "SHARED_ID" in result.reasons


def test_publication_support_alone_is_medium():
    assert _fit(publication_support_count=1).level == "MEDIUM"


def test_affiliation_needs_a_name_match_to_count_as_medium():
    assert _fit(name_evidence_count=1, ictu_affiliation_papers=1).level == "MEDIUM"
    assert _fit(ictu_affiliation_papers=1).level == "LOW"


def test_name_only_is_low_and_says_so():
    result = _fit(name_evidence_count=2)
    assert result.level == "LOW"
    assert "NAME_ONLY" in result.reasons


def test_nothing_to_go_on_is_insufficient():
    assert _fit().level == "INSUFFICIENT"


def test_several_ids_for_one_lecturer_is_only_a_note():
    result = _fit(name_evidence_count=2, is_ambiguous_lecturer=True)
    assert result.level == "LOW"
    assert "MULTIPLE_IDS_FOR_LECTURER" in result.reasons
