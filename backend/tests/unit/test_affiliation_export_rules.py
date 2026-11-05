"""Pure rules of the week-7 affiliation export (no database): unit choice, gap reasons, CSV."""

from __future__ import annotations

import csv
import io
from types import SimpleNamespace

import pytest

from app.services import author_affiliation as aa
from app.services.affiliation_export import (
    CSV_COLUMNS,
    GAP_REASONS,
    Decision,
    OverrideInput,
    Position,
    ResolutionInput,
    Unit,
    csv_bytes,
    decide_position,
    evidence_url_for,
    export_csv_rows,
)


def unit(text, status="CORROBORATED", source="openalex", url=None, orgs=()):
    return Unit(text, tuple(orgs), status, source, url)


def res(source, status, *, reason=None, presence=None, units=()):
    return ResolutionInput(source, status, reason, presence, tuple(units))


def pos(decision, *, order=1, name="Alpha, A.", lecturers=()):
    import uuid

    return Position(uuid.uuid4(), uuid.uuid4(), order, f"5720000000{order}", name, decision,
                    tuple(lecturers))


# ----------------------------------------------------------------------------- unit choice
def test_each_unit_keeps_the_confidence_of_its_own_source_and_verified_comes_first():
    d = decide_position(
        [
            res("openalex", "CORROBORATED", presence="PRESENT", units=[unit("Same text")]),
            res("crossref", "VERIFIED", presence="PRESENT",
                units=[unit("Same text", "VERIFIED", "crossref")]),
        ],
        [],
    )
    assert [(u.source, u.confidence) for u in d.units] == [
        ("crossref", "VERIFIED"), ("openalex", "CORROBORATED"),
    ]  # identical text from two sources is NOT merged
    assert d.affiliation_status == "VERIFIED" and d.gap_reason is None


def test_corroborated_override_replaces_automatic_units_and_is_never_verified():
    d = decide_position(
        [res("crossref", "VERIFIED", presence="PRESENT", units=[unit("Auto", "VERIFIED", "crossref")])],
        [OverrideInput("By hand", "CORROBORATED", "https://example.invalid/p")],
    )
    assert [(u.text, u.confidence, u.source) for u in d.units] == [("By hand", "MANUAL_REVIEW", "admin")]
    assert d.affiliation_status == "VERIFIED"  # the automatic status is untouched
    assert d.admin_reviewed and d.gap_reason is None


def test_unresolved_override_does_not_count_as_a_unit():
    d = decide_position(
        [res("crossref", "UNRESOLVED", reason="NAME_MISMATCH"),
         res("openalex", "UNRESOLVED", reason="NO_EXTERNAL_WORK")],
        [OverrideInput("Looked, unsure", "UNRESOLVED", "https://example.invalid/p")],
    )
    assert d.units == () and d.gap_reason == "ADMIN_MARKED_UNRESOLVED" and d.admin_reviewed


def test_unresolved_override_does_not_hide_automatic_units():
    d = decide_position(
        [res("openalex", "CORROBORATED", presence="PRESENT", units=[unit("Auto")])],
        [OverrideInput("Unsure", "UNRESOLVED", "https://example.invalid/p")],
    )
    assert [u.text for u in d.units] == ["Auto"] and d.gap_reason is None


def test_several_corroborated_overrides_keep_their_order():
    d = decide_position([], [OverrideInput("First", "CORROBORATED", "u1"),
                             OverrideInput("Second", "CORROBORATED", "u2")])
    assert [u.text for u in d.units] == ["First", "Second"]
    assert d.affiliation_status == "NOT_RECONCILED"


# ----------------------------------------------------------------------------- gap reasons
def test_no_resolution_means_not_reconciled():
    d = decide_position([], [])
    assert (d.affiliation_status, d.gap_reason, d.units) == ("NOT_RECONCILED", "NOT_RECONCILED", ())


def test_matched_source_without_unit_is_reported_as_such():
    d = decide_position(
        [res("crossref", "VERIFIED", presence="ABSENT"),
         res("openalex", "UNRESOLVED", reason="NO_EXTERNAL_WORK")],
        [],
    )
    assert d.gap_reason == "SOURCE_HAS_NO_AFFILIATION"
    assert {s.source: s.reason for s in d.by_source} == {
        "crossref": "SOURCE_HAS_NO_AFFILIATION", "openalex": "NO_EXTERNAL_WORK",
    }


def test_reason_with_most_progress_wins_over_no_work():
    d = decide_position(
        [res("crossref", "UNRESOLVED", reason="NO_EXTERNAL_WORK"),
         res("openalex", "UNRESOLVED", reason="NAME_MISMATCH")],
        [],
    )
    assert d.gap_reason == "NAME_MISMATCH"


@pytest.mark.parametrize("code", ["SOMETHING_NEW", None])
def test_unknown_reason_is_kept_in_the_list_as_unknown(code):
    assert decide_position([res("crossref", "UNRESOLVED", reason=code)], []).gap_reason == "UNKNOWN"


def test_trusted_resolution_marked_present_but_without_a_unit_is_unknown_not_lost():
    d = decide_position([res("crossref", "CORROBORATED", presence="PRESENT")], [])
    assert d.gap_reason == "UNKNOWN"


def test_every_reason_the_aligner_can_produce_has_a_place_in_the_list():
    produced = {v for k, v in vars(aa).items() if k.startswith("R_") and isinstance(v, str)}
    produced |= {"WITHHELD_SOURCE_CONFLICT", "DUPLICATE_DOI_IN_SOURCE"}
    assert produced <= set(GAP_REASONS), produced - set(GAP_REASONS)
    assert len(GAP_REASONS) == len(set(GAP_REASONS)) == 16


def test_every_position_is_in_exactly_one_group():
    cases = [
        decide_position([], []),
        decide_position([res("a", "UNRESOLVED", reason="ID_CONFLICT")], []),
        decide_position([res("a", "VERIFIED", presence="ABSENT")], []),
        decide_position([res("a", "CORROBORATED", presence="PRESENT", units=[unit("x")])], []),
        decide_position([], [OverrideInput("x", "CORROBORATED", "u")]),
        decide_position([], [OverrideInput("x", "UNRESOLVED", "u")]),
    ]
    for d in cases:
        assert bool(d.units) != (d.gap_reason is not None), d


# ----------------------------------------------------------------------------- evidence link
def test_evidence_link_is_a_url_a_person_can_open():
    assert evidence_url_for("openalex", "https://openalex.org/W1", None) == "https://openalex.org/W1"
    assert evidence_url_for("crossref", "10.1000/x.1", None) == "https://doi.org/10.1000/x.1"
    assert evidence_url_for("openalex", "W1", "10.1000/x.2") == "https://doi.org/10.1000/x.2"
    assert evidence_url_for("openalex", None, None) is None


# ----------------------------------------------------------------------------- CSV
def _pub(**kw):
    base = dict(eid="2-s2.0-1", doi="10.1/a", title="Title", year=2024, source_title="Journal")
    return SimpleNamespace(**{**base, **kw})


def parse(content: bytes):
    assert content.startswith(b"\xef\xbb\xbf"), "Excel needs the BOM for Vietnamese"
    assert b"\r\n" in content and b"\n" not in content.replace(b"\r\n", b"")
    return list(csv.reader(io.StringIO(content.decode("utf-8-sig"), newline="")))


def test_csv_has_the_sixteen_contract_columns_and_one_row_per_position():
    d1 = decide_position(
        [res("crossref", "VERIFIED", presence="PRESENT", units=[unit("Univ X", "VERIFIED", "crossref", "https://doi.org/10.1/a")]),
         res("openalex", "CORROBORATED", presence="PRESENT", units=[unit("Univ X", "CORROBORATED", "openalex", "https://openalex.org/W1")])],
        [],
    )
    d2 = decide_position([res("crossref", "UNRESOLVED", reason="NAME_MISMATCH")], [])
    rows = parse(csv_bytes(CSV_COLUMNS, export_csv_rows(
        [(_pub(), [pos(d1, lecturers=["Lecturer A"]), pos(d2, order=2)])])))
    assert rows[0] == list(CSV_COLUMNS) and len(CSV_COLUMNS) == 16
    assert len(rows) == 3 and all(len(r) == 16 for r in rows)
    first, second = (dict(zip(CSV_COLUMNS, r)) for r in rows[1:])
    assert first["author_count"] == "2" and first["ictu_lecturer"] == "Lecturer A"
    # several units: one row, parallel columns in the same order
    assert first["affiliation"] == "Univ X | Univ X"
    assert first["confidence"] == "VERIFIED | CORROBORATED"
    assert first["source"] == "crossref | openalex"
    assert first["evidence_url"] == "https://doi.org/10.1/a | https://openalex.org/W1"
    assert (second["affiliation"], second["gap_reason"]) == ("", "NAME_MISMATCH")


def test_publication_without_authors_still_gets_a_row_with_zero_count():
    rows = parse(csv_bytes(CSV_COLUMNS, export_csv_rows([(_pub(), [])])))
    assert len(rows) == 2 and len(rows[1]) == 16
    row = dict(zip(CSV_COLUMNS, rows[1]))
    assert row["eid"] == "2-s2.0-1" and row["author_count"] == "0" and row["author_order"] == ""


def test_text_from_outside_cannot_start_a_spreadsheet_formula():
    d = decide_position([], [OverrideInput("=HYPERLINK(\"http://x\")", "CORROBORATED", "+u")])
    rows = parse(csv_bytes(CSV_COLUMNS, export_csv_rows(
        [(_pub(title="@SUM(A1)", source_title="-1+1"), [pos(d, name="\tTab")])])))
    row = dict(zip(CSV_COLUMNS, rows[1]))
    assert row["title"] == "'@SUM(A1)" and row["source_title"] == "'-1+1"
    assert row["affiliation"].startswith("'=") and row["evidence_url"] == "'+u"
    assert row["author_name"] == "'\tTab"
    assert row["year"] == "2024" and row["author_count"] == "1"  # numbers are left alone


def test_a_separator_inside_a_unit_does_not_break_column_alignment():
    d = decide_position([], [OverrideInput("Dept A | Dept B", "CORROBORATED", "u1"),
                             OverrideInput("Dept C", "CORROBORATED", "u2")])
    row = dict(zip(CSV_COLUMNS, parse(csv_bytes(CSV_COLUMNS, export_csv_rows([(_pub(), [pos(d)])])))[1]))
    assert row["affiliation"].split(" | ") == ["Dept A / Dept B", "Dept C"]
    assert len(row["confidence"].split(" | ")) == len(row["affiliation"].split(" | ")) == 2


def test_vietnamese_text_survives_the_round_trip():
    d = decide_position([], [OverrideInput("Trường Đại học Công nghệ Thông tin và Truyền thông", "CORROBORATED", "u")])
    rows = parse(csv_bytes(CSV_COLUMNS, export_csv_rows([(_pub(title="Nghiên cứu ứng dụng"), [pos(d)])])))
    row = dict(zip(CSV_COLUMNS, rows[1]))
    assert row["affiliation"] == "Trường Đại học Công nghệ Thông tin và Truyền thông"
    assert row["title"] == "Nghiên cứu ứng dụng"


def test_decision_type_is_immutable():
    d = decide_position([], [])
    assert isinstance(d, Decision)
    with pytest.raises(AttributeError):
        d.gap_reason = "X"  # type: ignore[misc]
