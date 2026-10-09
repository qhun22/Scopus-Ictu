"""Task 17: diacritic-insensitive search helpers (read-only search, never used by matching)."""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from app.services.text_folding import _FROM, _TO, escaped_substring_pattern, fold_text


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Lương Thị Minh Huế", "luong thi minh hue"),
        ("Đặng Quang Á", "dang quang a"),
        ("NGUYỄN VĂN", "nguyen van"),
        ("Nguyen, Thi Hang", "nguyen, thi hang"),
        ("60319803200", "60319803200"),
    ],
)
def test_fold_text(value: str, expected: str) -> None:
    assert fold_text(value) == expected


def test_translation_tables_have_equal_length_and_ascii_targets() -> None:
    assert len(_FROM) == len(_TO)
    assert all(ord(ch) < 128 for ch in _TO)


def test_pattern_escapes_like_wildcards() -> None:
    assert escaped_substring_pattern(" 50%_x ") == "%50\\%\\_x%"


def test_sql_translate_matches_python_folding(isolated_db_engine) -> None:
    if isolated_db_engine is None:
        pytest.skip("No isolated test database available.")
    sample = "Nguyễn Văn Đặng — ƯỚC MƠ"
    with isolated_db_engine.connect() as conn:
        value = conn.execute(
            text("select translate(lower(:v), :f, :t)"), {"v": sample, "f": _FROM, "t": _TO}
        ).scalar_one()
    # ASCII letters are lower-cased by SQL lower(); accented ones by the explicit map.
    assert value.startswith("nguyen van dang")
    assert "uoc mo" in value
