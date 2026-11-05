"""Focused tests for deterministic transient candidate generation."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.matching.candidate_generator import (
    OBSERVED_TITLE_PREFIXES,
    drop_unsupported_token_set_candidates,
    generate_candidates,
    has_observed_title_prefix,
    is_token_set_only,
    normalize_comma_equivalence,
    normalize_name_n2,
    normalize_token_set_equivalence,
    strip_observed_title_prefix,
)


def lecturer(name: str) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), full_name=name)


def author(name: str, scopus_id: str = "10000000000") -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), scopus_id=scopus_id, preferred_name=name)


def variant(author_id, variant_type: str, name: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        scopus_author_id=author_id,
        variant_type=variant_type,
        variant_name=name,
    )


def run(lecturers, authors, variants=()):
    return generate_candidates(lecturers, authors, variants)


def rule_ids(candidate):
    return {evidence.rule_id for evidence in candidate.evidence}


def test_n0_exact_match_and_different_value() -> None:
    matching_lecturer = lecturer("Nguyen Van A")
    different_lecturer = lecturer("Nguyen Van B")
    scopus_author = author("Nguyen Van A")

    results = run([matching_lecturer, different_lecturer], [scopus_author])

    assert [(item.lecturer_id, item.scopus_author_id) for item in results] == [
        (matching_lecturer.id, scopus_author.id)
    ]
    assert rule_ids(results[0]) == {"RULE_EXACT_N0"}


@pytest.mark.parametrize("prefix", OBSERVED_TITLE_PREFIXES)
def test_every_supported_title_prefix_is_stripped(prefix: str) -> None:
    lecturer_row = lecturer(f"{prefix} Nguyen Van A")
    scopus_author = author("Nguyen, Van A")

    assert has_observed_title_prefix(lecturer_row.full_name)
    assert strip_observed_title_prefix(lecturer_row.full_name) == "Nguyen Van A"
    assert len(run([lecturer_row], [scopus_author])) == 1


@pytest.mark.parametrize("prefix", ["Khác.", "ĐH.", "Prof.", "TSX."])
def test_unknown_or_non_title_prefix_is_not_stripped(prefix: str) -> None:
    lecturer_row = lecturer(f"{prefix} Nguyen Van A")
    scopus_author = author("Nguyen, Van A")

    assert not has_observed_title_prefix(lecturer_row.full_name)
    assert strip_observed_title_prefix(lecturer_row.full_name) == lecturer_row.full_name
    assert run([lecturer_row], [scopus_author]) == ()


def test_title_prefix_requires_a_token_boundary() -> None:
    lecturer_row = lecturer("TS.Nguyen Van A")
    scopus_author = author("Nguyen, Van A")

    assert not has_observed_title_prefix(lecturer_row.full_name)
    assert run([lecturer_row], [scopus_author]) == ()


def test_diacritic_fold_is_weaker_than_exact_name() -> None:
    lecturer_row = lecturer("TS. Nguyễn Văn A")
    scopus_author = author("Nguyen Van A")

    results = run([lecturer_row], [scopus_author])

    assert len(results) == 1
    assert "RULE_EXACT_N0" not in rule_ids(results[0])
    assert "RULE_TITLE_STRIPPED_N2" in rule_ids(results[0])
    assert "RULE_TITLE_STRIPPED_N2_FORMAT" not in rule_ids(results[0])


def test_vietnamese_d_folds_deterministically() -> None:
    assert normalize_name_n2("Đinh") == normalize_name_n2("Dinh")
    assert normalize_name_n2("Đặng") == "dang"


def test_comma_equivalence_preserves_token_order() -> None:
    lecturer_row = lecturer("TS. Nguyen Van A")
    scopus_author = author("Nguyen, Van A")

    results = run([lecturer_row], [scopus_author])

    assert len(results) == 1
    assert normalize_comma_equivalence("Nguyen, Van A") == "nguyen van a"
    assert "RULE_TITLE_STRIPPED_N2_FORMAT" in rule_ids(results[0])


def test_hyphen_is_not_silently_normalized() -> None:
    lecturer_row = lecturer("TS. Nguyễn Đức Bình")
    scopus_author = author("Nguyen, Duc-Binh")

    assert run([lecturer_row], [scopus_author]) == ()


def test_title_prefixed_lecturer_is_not_matched_in_a_different_word_order() -> None:
    # The word-order rule does not strip academic titles, so a prefixed name never matches it.
    lecturer_row = lecturer("TS. Nguyen Van A")
    scopus_author = author("Van A Nguyen")

    assert run([lecturer_row], [scopus_author]) == ()


def test_same_words_in_a_different_order_are_proposed_only_by_the_token_set_rule() -> None:
    lecturer_row = lecturer("Nguyen Van A")
    scopus_author = author("Van A Nguyen")

    results = run([lecturer_row], [scopus_author])

    assert [(item.lecturer_id, item.scopus_author_id) for item in results] == [
        (lecturer_row.id, scopus_author.id)
    ]
    assert rule_ids(results[0]) == {"RULE_TOKEN_SET"}


def test_token_set_rule_folds_diacritics_comma_and_hyphen() -> None:
    lecturer_row = lecturer("Nguyễn Đức Bình")
    scopus_author = author("Binh, Nguyen-Duc")

    results = run([lecturer_row], [scopus_author])

    assert len(results) == 1
    assert rule_ids(results[0]) == {"RULE_TOKEN_SET"}
    assert normalize_token_set_equivalence("Nguyễn Đức Bình") == "binh duc nguyen"
    assert normalize_token_set_equivalence("Binh, Nguyen-Duc") == "binh duc nguyen"


def test_token_set_rule_does_not_match_different_words() -> None:
    assert run([lecturer("Nguyen Van A")], [author("Van B Nguyen")]) == ()


def test_token_set_rule_ignores_single_word_names() -> None:
    assert normalize_token_set_equivalence("Nguyen") == ""
    assert run([lecturer("Nguyen")], [author("Nguyen", "10000000001")]) != ()
    only_token_set = run([lecturer("Nguyen")], [author("nguyen,", "10000000002")])
    assert all("RULE_TOKEN_SET" not in rule_ids(item) for item in only_token_set)


def test_token_set_rule_never_adds_evidence_to_a_pair_an_ordered_rule_found() -> None:
    lecturer_row = lecturer("Nguyen Van A")
    scopus_author = author("Nguyen Van A")
    reordered = variant(scopus_author.id, "AUTHOR_DISPLAY", "A Van Nguyen")

    results = run([lecturer_row], [scopus_author], [reordered])

    assert len(results) == 1
    assert rule_ids(results[0]) == {"RULE_EXACT_N0"}


def test_token_set_rule_is_the_lowest_priority_rule() -> None:
    from app.services.matching.candidate_generator import RULE_ORDER

    assert RULE_ORDER[-1] == "RULE_TOKEN_SET"


def test_gate_drops_a_token_set_only_pair_without_ictu_evidence() -> None:
    lecturer_row = lecturer("Tran Thi Mai")
    scopus_author = author("Mai Tran Thi")
    results = run([lecturer_row], [scopus_author])

    assert is_token_set_only(results[0])
    assert drop_unsupported_token_set_candidates(results, {}) == ()
    assert drop_unsupported_token_set_candidates(results, {scopus_author.id: 0}) == ()


def test_gate_keeps_a_token_set_only_pair_with_ictu_evidence() -> None:
    lecturer_row = lecturer("Tran Thi Mai")
    scopus_author = author("Mai Tran Thi")
    results = run([lecturer_row], [scopus_author])

    kept = drop_unsupported_token_set_candidates(results, {scopus_author.id: 1})

    assert kept == results


def test_gate_never_touches_a_pair_an_ordered_rule_found() -> None:
    lecturer_row = lecturer("Nguyen Van A")
    scopus_author = author("Nguyen Van A")
    results = run([lecturer_row], [scopus_author])

    assert not is_token_set_only(results[0])
    assert drop_unsupported_token_set_candidates(results, {}) == results


def test_token_set_candidates_are_deterministic() -> None:
    lecturers = [lecturer("Tran Thi Mai"), lecturer("Le Van Hung")]
    authors = [author("Mai Tran Thi", "10000000003"), author("Hung, Le Van", "10000000004")]

    assert run(lecturers, authors) == run(lecturers, authors)


def test_scopus_collision_preserves_two_author_candidates() -> None:
    lecturer_row = lecturer("Nguyen Van A")
    first = author("Nguyen Van A", "10000000001")
    second = author("Nguyen Van A", "10000000002")

    results = run([lecturer_row], [first, second])

    assert {item.scopus_id for item in results} == {"10000000001", "10000000002"}


def test_lecturer_collision_preserves_independent_candidate_sets() -> None:
    first = lecturer("Nguyen Van A")
    second = lecturer("Nguyen Van A")
    scopus_author = author("Nguyen Van A")

    results = run([first, second], [scopus_author])

    assert {(item.lecturer_id, item.scopus_author_id) for item in results} == {
        (first.id, scopus_author.id),
        (second.id, scopus_author.id),
    }


def test_multiple_surfaces_create_one_pair_and_multiple_evidence_descriptors() -> None:
    lecturer_row = lecturer("Nguyen Van A")
    scopus_author = author("Nguyen Van A")
    variants = [
        variant(scopus_author.id, "AUTHOR_FULL_NAME", "Nguyen Van A"),
        variant(scopus_author.id, "AUTHOR_DISPLAY", "Nguyen Van A"),
    ]

    results = run([lecturer_row], [scopus_author], variants)

    assert len(results) == 1
    assert len(results[0].evidence) == 3
    assert {item.scopus_surface_type for item in results[0].evidence} == {
        "PREFERRED_NAME",
        "AUTHOR_FULL_NAME",
        "AUTHOR_DISPLAY",
    }


def test_rerun_is_deterministic() -> None:
    lecturer_row = lecturer("TS. Nguyễn Văn A")
    first = author("Nguyen, Van A", "10000000001")
    second = author("Nguyen, Van A", "10000000002")
    variants = [
        variant(first.id, "AUTHOR_FULL_NAME", "Nguyen, Van A"),
        variant(second.id, "AUTHOR_DISPLAY", "Nguyen V.A."),
    ]

    first_run = run([lecturer_row], [second, first], variants)
    second_run = run([lecturer_row], [second, first], variants)

    assert first_run == second_run
    assert [item.scopus_id for item in first_run] == sorted(
        item.scopus_id for item in first_run
    )
