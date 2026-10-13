"""Tests for Tiered Token Strength Matching in Craw-assisted discovery.

Validates the proposed Tiered Token Strength algorithm on both POSITIVE and NEGATIVE cases:
- Positive cases: Known valid matches (including abbreviations, hyphenated names, academic title prefixes) MUST pass.
- Negative cases: Vietnamese co-authors sharing common surnames ("Nguyen", "Tran", "Le") or middle names ("Van", "Thi")
  MUST be rejected as unattributed publication evidence, eliminating false positives.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.services.matching.candidate_generator import normalize_name_n2, strip_observed_title_prefix

# ---------------------------------------------------------------------------
# TIERED TOKEN STRENGTH ALGORITHM DEFINITION (PHƯƠNG ÁN 2 THIẾT KẾ CẢI TIẾN)
# ---------------------------------------------------------------------------

GENERIC_VIETNAMESE_TOKENS: frozenset[str] = frozenset(
    {
        # Common surnames
        "nguyen", "tran", "le", "pham", "hoang", "huynh", "phan", "vu", "vo",
        "dang", "bui", "do", "ho", "ngo", "duong", "dinh", "ly", "dao", "doan",
        "luong", "thai", "trinh", "mai", "cao", "truong", "ha",
        # Common middle names
        "van", "thi", "dinh", "duc", "thanh", "huu", "ngoc", "quang", "minh",
        "xuan", "kim", "hai", "tien", "cong", "duy", "anh",
    }
)

_MIN_TOKEN_LEN = 2


@dataclass(frozen=True, slots=True)
class ParsedNameStructure:
    raw: str
    normalized: str
    tokens: tuple[str, ...]
    surname: str | None
    given_name: str | None
    middle_tokens: tuple[str, ...]
    initials: frozenset[str]


def parse_vietnamese_name(full_name: str) -> ParsedNameStructure:
    """Parse Vietnamese full name into structured components (Họ, Đệm, Tên chính).
    Strips academic prefixes (PGS.TS., ThS., TS., etc.) first.
    """
    stripped = strip_observed_title_prefix(full_name)
    normalized = normalize_name_n2(stripped)
    raw_tokens = tuple(re.split(r"[\s,\-\.]+", normalized))
    tokens = tuple(t for t in raw_tokens if len(t) >= 1)

    if not tokens:
        return ParsedNameStructure(full_name, normalized, (), None, None, (), frozenset())

    surname = tokens[0] if len(tokens[0]) >= _MIN_TOKEN_LEN else None
    given_name = tokens[-1] if len(tokens[-1]) >= _MIN_TOKEN_LEN else None
    middle = tokens[1:-1] if len(tokens) > 2 else ()
    initials = frozenset(t[0] for t in tokens if len(t) >= 1)

    return ParsedNameStructure(
        raw=full_name,
        normalized=normalized,
        tokens=tokens,
        surname=surname,
        given_name=given_name,
        middle_tokens=middle,
        initials=initials,
    )


def parse_scopus_surface(surface: str) -> ParsedNameStructure:
    """Parse a Scopus author name surface (e.g. 'Nguyen, Van-Nui' or 'Nguyen, V.-N.').
    Handles commas, hyphens, and initials.
    """
    normalized = normalize_name_n2(surface)
    raw_tokens = tuple(re.split(r"[\s,\-\.]+", normalized))
    tokens = tuple(t for t in raw_tokens if len(t) >= 1)

    if not tokens:
        return ParsedNameStructure(surface, normalized, (), None, None, (), frozenset())

    # In Scopus 'Surname, Given/Initials', the first token before comma is typically surname
    # We identify full tokens vs single-letter initials
    surname = tokens[0] if len(tokens[0]) >= _MIN_TOKEN_LEN else None
    initials = frozenset(t[0] for t in tokens if len(t) >= 1)

    # Candidate given name in Scopus: the Vietnamese convention this dataset's
    # surfaces follow even after the comma is "Surname, [Middle...] Given" —
    # the given name is the LAST non-initial token, not the first. Picking
    # the first token here was the original bug: for "Nguyen, Van-Nui" it
    # extracted "van" (a middle name) as the given name instead of "nui",
    # which then made Rule 1 (given-name conflict) wrongly reject correct
    # matches whenever the Scopus surface listed the middle name before the
    # given name (observed in real data, e.g. "Nguyen, Van-Nui").
    other_tokens = [t for t in tokens[1:] if len(t) >= _MIN_TOKEN_LEN]
    given_name = other_tokens[-1] if other_tokens else None
    middle = tuple(other_tokens[:-1]) if len(other_tokens) > 1 else ()

    return ParsedNameStructure(
        raw=surface,
        normalized=normalized,
        tokens=tokens,
        surname=surname,
        given_name=given_name,
        middle_tokens=middle,
        initials=initials,
    )


def evaluate_tiered_name_correspondence(
    lecturer_name: str,
    scopus_surfaces: list[str],
) -> tuple[bool, str]:
    """Tiered Token Strength evaluation for name correspondence.
    
    Returns:
        (is_match, reason)
    
    Rules:
    1. GIVEN-NAME CONFLICT REJECTION:
       If both lecturer and Scopus author have full given names and they CONFLICT (e.g. 'An' vs 'Binh'),
       REJECT immediately. Sharing 'Nguyen' or 'Van' does NOT override a conflicting given name.
    2. STRONG STRUCTURAL CORRESPONDENCE (Positive):
       - Given name matches AND at least one other token (surname or middle) matches.
    3. INITIALS-CORROBORATED CORRESPONDENCE (Positive for abbreviations):
       - Surname matches AND the initial of lecturer's given name appears in author's initials
         AND no conflicting given name exists.
    4. GENERIC-ONLY TOKEN REJECTION (Negative):
       - Only generic tokens (e.g. solely 'Nguyen' or solely 'Van') match without given-name confirmation -> REJECT.
    """
    lec = parse_vietnamese_name(lecturer_name)
    if not lec.tokens:
        return False, "EMPTY_LECTURER_NAME"

    parsed_surfaces = [parse_scopus_surface(s) for s in scopus_surfaces if s]
    if not parsed_surfaces:
        return False, "NO_SCOPUS_SURFACES"

    for surf in parsed_surfaces:
        # Check Rule 1: Given Name Conflict
        if lec.given_name and surf.given_name:
            if lec.given_name != surf.given_name:
                # Conflicting given names on the same paper -> Different person!
                continue

        # Check Rule 2: Given name matches
        if lec.given_name and surf.given_name and lec.given_name == surf.given_name:
            # Check if surname or middle name also corroborates
            shared_others = set(lec.tokens) & set(surf.tokens) - {lec.given_name}
            if shared_others:
                return True, f"STRONG_MATCH_GIVEN_AND_OTHER({lec.given_name},{shared_others})"

        # Check Rule 3: Abbreviated initial match
        if lec.surname and surf.surname and lec.surname == surf.surname:
            if lec.given_name and lec.given_name[0] in surf.initials:
                # No conflicting given name detected
                if not (surf.given_name and surf.given_name != lec.given_name):
                    return True, f"INITIALS_MATCH({lec.surname},{lec.given_name[0]})"

        # Check if full tokens set has non-generic token match
        shared_tokens = (set(t for t in lec.tokens if len(t) >= _MIN_TOKEN_LEN) &
                         set(t for t in surf.tokens if len(t) >= _MIN_TOKEN_LEN))
        distinctive_shared = shared_tokens - GENERIC_VIETNAMESE_TOKENS
        if distinctive_shared and lec.surname and surf.surname and lec.surname == surf.surname:
            return True, f"DISTINCTIVE_TOKEN_MATCH({distinctive_shared})"

    return False, "NO_SUFFICIENT_STRUCTURAL_CORRESPONDENCE"


# ---------------------------------------------------------------------------
# UNIT TESTS: POSITIVE VALID CASES (KHÔNG ĐƯỢC BỎ SÓT)
# ---------------------------------------------------------------------------

def test_pos_1_academic_title_with_hyphenated_name() -> None:
    """PGS.TS. Nguyễn Văn Núi vs Nguyen, Van-Nui: Must MATCH."""
    is_match, reason = evaluate_tiered_name_correspondence(
        "PGS.TS. Nguyễn Văn Núi", ["Nguyen, Van-Nui", "Nguyen, Van Nui"]
    )
    assert is_match is True
    assert "STRONG_MATCH" in reason or "DISTINCTIVE" in reason


def test_pos_2_full_vietnamese_order() -> None:
    """ThS. Trần Thị Mai vs Tran Thi Mai: Must MATCH."""
    is_match, reason = evaluate_tiered_name_correspondence(
        "ThS. Trần Thị Mai", ["Tran Thi Mai", "Tran, Thi Mai"]
    )
    assert is_match is True


def test_pos_3_abbreviated_initials_matching_given_name() -> None:
    """Nguyễn Văn Bình vs Nguyen, V.-B.: Must MATCH (initials b matches Binh)."""
    is_match, reason = evaluate_tiered_name_correspondence(
        "Nguyễn Văn Bình", ["Nguyen, V.-B."]
    )
    assert is_match is True
    assert "INITIALS_MATCH" in reason


def test_pos_4_unaccented_unicode_folding() -> None:
    """Đặng Thị Thảo vs Dang, Thi Thao: Must MATCH (D folding and tone stripping)."""
    is_match, reason = evaluate_tiered_name_correspondence(
        "Đặng Thị Thảo", ["Dang, Thi Thao"]
    )
    assert is_match is True


def test_pos_5_variant_name_recovers_match() -> None:
    """When preferred name is abbreviated but variants contain full name."""
    is_match, reason = evaluate_tiered_name_correspondence(
        "Vũ Thị Hoa", ["Vu, T.", "Vu Thi Hoa"]
    )
    assert is_match is True


def test_pos_6_three_word_name_distinctive() -> None:
    """Bùi Quang Huy vs Bui, Quang Huy: Must MATCH."""
    is_match, reason = evaluate_tiered_name_correspondence(
        "Bùi Quang Huy", ["Bui, Quang Huy"]
    )
    assert is_match is True


# ---------------------------------------------------------------------------
# UNIT TESTS: NEGATIVE CASES (CHỐNG FALSE POSITIVE ĐỒNG TÁC GIẢ)
# ---------------------------------------------------------------------------

def test_neg_1_coauthor_same_surname_different_given_name_rejected() -> None:
    """Nguyễn Văn An vs Nguyễn Thị Bình (Co-authors sharing surname Nguyen).
    Given names 'An' vs 'Binh' CONFLICT -> Must REJECT!
    """
    is_match, reason = evaluate_tiered_name_correspondence(
        "Nguyễn Văn An", ["Nguyen, Thi Binh"]
    )
    assert is_match is False
    assert reason == "NO_SUFFICIENT_STRUCTURAL_CORRESPONDENCE"


def test_neg_2_coauthor_same_middle_name_different_given_name_rejected() -> None:
    """Nguyễn Văn An vs Trần Văn Cường (Co-authors sharing middle name Van).
    Given names 'An' vs 'Cuong' and surnames 'Nguyen' vs 'Tran' CONFLICT -> Must REJECT!
    """
    is_match, reason = evaluate_tiered_name_correspondence(
        "Nguyễn Văn An", ["Tran, Van Cuong"]
    )
    assert is_match is False


def test_neg_3_coauthor_same_surname_and_middle_different_given_name_rejected() -> None:
    """Nguyễn Văn An vs Nguyễn Văn Cường.
    Even though they share BOTH 'Nguyen' and 'Van', their given names 'An' vs 'Cuong' CONFLICT!
    Must REJECT!
    """
    is_match, reason = evaluate_tiered_name_correspondence(
        "Nguyễn Văn An", ["Nguyen, Van Cuong"]
    )
    assert is_match is False


def test_neg_4_single_generic_surname_only_rejected() -> None:
    """Solely sharing generic surname without initials or given name match -> Must REJECT."""
    is_match, reason = evaluate_tiered_name_correspondence(
        "Lê Văn Phúc", ["Le, M."]  # 'M' does not match 'P' of Phuc
    )
    assert is_match is False


def test_neg_5_completely_unrelated_foreign_authors_rejected() -> None:
    """Foreign co-authors on the same paper -> Must REJECT."""
    is_match, reason = evaluate_tiered_name_correspondence(
        "Nguyễn Văn Núi", ["Smith, John", "Garcia, Maria", "Zhang, Wei"]
    )
    assert is_match is False
