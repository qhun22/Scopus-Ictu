"""Diacritic-insensitive text search helpers (read-only search only).

Used ONLY by search/list queries so that "Luong" finds "Lương" and vice versa.
It must never be used by the matching engine: candidate matching keeps its own
documented normalisation rules (``candidate_generator``) and is unchanged.

No PostgreSQL extension (``unaccent``) and therefore no migration is needed:
folding is done with ``translate()`` over the Vietnamese letters.  ``lower()`` is
locale dependent (the demo cluster uses the ``C`` locale and does not lower-case
non-ASCII letters), so uppercase accented letters are mapped explicitly as well.
"""

from __future__ import annotations

import unicodedata

from sqlalchemy import func
from sqlalchemy.sql.elements import ColumnElement

_VI_LOWER = (
    "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
)


def fold_text(value: str) -> str:
    """Lower-case, strip diacritics and map đ -> d (Python side)."""
    lowered = unicodedata.normalize("NFC", value).casefold().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", lowered)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


_FROM = _VI_LOWER + _VI_LOWER.upper()
_TO = "".join(fold_text(ch) for ch in _FROM)
assert len(_FROM) == len(_TO)


def folded(column: ColumnElement) -> ColumnElement:
    """SQL expression: the column lower-cased with Vietnamese diacritics removed."""
    return func.translate(func.lower(column), _FROM, _TO)


def escaped_substring_pattern(value: str) -> str:
    """LIKE pattern (``\\`` escape) for a folded, literal substring search."""
    folded_value = fold_text(value.strip())
    escaped = folded_value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def contains_folded(column: ColumnElement, term: str) -> ColumnElement:
    """``column`` contains ``term`` ignoring case and Vietnamese diacritics."""
    return folded(column).like(escaped_substring_pattern(term), escape="\\")


__all__ = ["fold_text", "folded", "escaped_substring_pattern", "contains_folded"]
