from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.api.v1.endpoints.lecturers import (
    _get_duplicate_lecturer_ids,
    _get_lecturer_stats,
)
from app.services.lecturer_dataset.importer import _ambiguous_name_candidate


def test_duplicate_warning_ids_ignore_academic_title_prefixes() -> None:
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    normal_id = uuid.uuid4()
    db = MagicMock()
    db.execute.return_value.all.return_value = [
        (first_id, "ĐH. Nguyễn Văn An", "đh. nguyễn văn an"),
        (second_id, "ThS. Nguyễn Văn An", "ths. nguyễn văn an"),
        (normal_id, "TS. Trần Thị Bình", "ts. trần thị bình"),
    ]

    assert _get_duplicate_lecturer_ids(db) == {first_id, second_id}


def test_same_name_with_different_emails_is_not_a_warning() -> None:
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    db = MagicMock()
    db.execute.return_value.all.return_value = [
        (
            first_id,
            "ThS. Nguyễn Thị Dung",
            "ths. nguyễn thị dung",
            "dungnt@ictu.edu.vn",
            None,
        ),
        (
            second_id,
            "ThS. Nguyễn Thị Dung",
            "ths. nguyễn thị dung",
            "ntdung@ictu.edu.vn",
            None,
        ),
    ]

    assert _get_duplicate_lecturer_ids(db) == set()


def test_same_email_on_different_names_marks_both_profiles_as_warning() -> None:
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    db = MagicMock()
    db.execute.return_value.all.return_value = [
        (first_id, "Đặng Quang Á", "đặng quang á", "hqtien@ictu.edu.vn", "Khoa CNTT"),
        (second_id, "Hà Quang Tiến", "hà quang tiến", "HQTien@ictu.edu.vn", "Khoa CNTT"),
    ]

    assert _get_duplicate_lecturer_ids(db) == {first_id, second_id}


def test_import_name_collision_uses_email_as_discriminator() -> None:
    candidate_id = uuid.uuid4()
    candidates = [(candidate_id, "first@ictu.edu.vn")]

    assert _ambiguous_name_candidate(candidates, "second@ictu.edu.vn") is None
    assert _ambiguous_name_candidate(candidates, None) == candidate_id


def test_lecturer_stats_publish_warning_count() -> None:
    db = MagicMock()
    db.scalar.side_effect = [5, 1, 0]
    db.execute.return_value.all.return_value = [
        (uuid.uuid4(), "ThS. Lê Anh Tú", "ths. lê anh tú"),
        (uuid.uuid4(), "ThS. Lê Anh Tú", "ths. lê anh tú"),
        (uuid.uuid4(), "TS. Hoàng Văn Nam", "ts. hoàng văn nam"),
    ]

    stats = _get_lecturer_stats(db)

    assert stats.warning_count == 2
    assert stats.total_lecturers == 5


def test_lecturer_stats_do_not_hide_duplicate_query_failures() -> None:
    db = MagicMock()
    db.scalar.side_effect = [5, 1, 0]
    db.execute.side_effect = RuntimeError("duplicate query failed")

    with pytest.raises(RuntimeError, match="duplicate query failed"):
        _get_lecturer_stats(db)
