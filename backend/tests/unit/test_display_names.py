"""Task 14: exact display-name repair (does not touch legitimate names containing '?')."""

import pytest

from app.core.display_names import ADMIN_LABEL, is_corrupted_name, repair_display_name


@pytest.mark.parametrize("name", ["Qu?n tr? vi?n", "qu?n tr? vi?n", "  Qu?n tr? vi?n ", "???", " ? ? "])
def test_known_corruption_is_repaired_for_admin(name) -> None:
    assert is_corrupted_name(name)
    assert repair_display_name(name, "ADMIN") == ADMIN_LABEL


def test_exact_admin_label_corruption_is_repaired_even_without_role() -> None:
    assert repair_display_name("Qu?n tr? vi?n") == ADMIN_LABEL


@pytest.mark.parametrize("name", ["Quản trị viên", "Nguyễn Văn A", "Who? Me", "Hà Nội?", "Dr. O'Neil (?)", "", None])
def test_other_names_are_never_rewritten(name) -> None:
    assert repair_display_name(name, "ADMIN") == name


def test_placeholder_only_name_for_non_admin_is_left_alone() -> None:
    assert repair_display_name("???", "LECTURER") == "???"
