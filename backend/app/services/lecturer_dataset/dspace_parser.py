"""DSpace-archive HTML parser — extract lecturer records from
``https://repository.ictu.edu.vn/giang-vien/`` archive pages.

The DSpace archive is a WordPress-rendered page (slug ``giang-vien/``)
where every lecturer is wrapped in an ``<article class="gv-card dl-card"``
element carrying schema.org ``Person`` microdata plus a stable ``data-*``
attribute block (``data-name``, ``data-rank``, ``data-degree``,
``data-position``). Each card also exposes:

* ``itemprop="name"`` + ``itemprop="url"`` — display name + profile URL
* ``itemprop="jobTitle"`` — position / role
* ``itemprop="honorificPrefix"`` — academic rank + degree (``PGS – TS`` etc.)
* ``itemprop="knowsAbout"`` — specialisation
* ``itemprop="email"`` + ``mailto:...`` — institutional email

The parser is intentionally pure-stdlib, deterministic and uses
attribute-scoped regex extraction (instead of a full HTML parser) so
that the builder runs reliably against the cached HTML snapshot in
``data/lecturers/raw/`` without depending on any third-party HTML
parser. The structural HTML emitted by the DSpace WordPress theme is
stable: each ``<article class="gv-card …">`` block is self-contained
and its body does not contain nested ``<article>`` elements.

M2.5A source-of-truth: ``https://repository.ictu.edu.vn/giang-vien/``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass


DSPACE_SOURCE_URL = "https://repository.ictu.edu.vn/giang-vien/"
DSPACE_SOURCE_SYSTEM = "ictu_dspace_archive"
DSPACE_SOURCE_LABEL = (
    "ICTU official DSpace repository — lecturer archive (Vietnamese)"
)


# ---------------------------------------------------------------------------
# Card-level extraction
# ---------------------------------------------------------------------------


_ARTICLE_OPEN_RE = re.compile(
    r'<article\b[^>]*class="[^"]*\bgv-card\b[^"]*"[^>]*>',
    re.IGNORECASE,
)
_ARTICLE_CLOSE_RE = re.compile(r"</article\s*>", re.IGNORECASE)

# Per-article attributes we care about.
_ATTR_DATA_NAME_RE = re.compile(r'\bdata-name="([^"]*)"', re.IGNORECASE)
_ATTR_DATA_RANK_RE = re.compile(r'\bdata-rank="([^"]*)"', re.IGNORECASE)
_ATTR_DATA_DEGREE_RE = re.compile(r'\bdata-degree="([^"]*)"', re.IGNORECASE)
_ATTR_DATA_POSITION_RE = re.compile(r'\bdata-position="([^"]*)"', re.IGNORECASE)

# Body-level microdata we care about.
_NAME_ANCHOR_RE = re.compile(
    r'<a\b[^>]*\bitemprop="url"[^>]*>(?P<name>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_HREF_RE = re.compile(r'\bhref="([^"]+)"', re.IGNORECASE)
_ITEMPROP_BODY_RE = re.compile(
    r'\bitemprop="(?P<key>[^"]+)"[^>]*>(?P<body>.*?)<',
    re.IGNORECASE | re.DOTALL,
)
_EMAIL_MAILTO_RE = re.compile(
    r'\bhref="mailto:(?P<email>[^?"]+)[?"]',
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")

# Mapping for ``data-rank`` / ``data-degree`` defensive fallback.
_RANK_DEGREE_MAP: dict[str, tuple[str | None, str | None]] = {
    "gs": ("TS", "GS"),
    "pgs": ("TS", "PGS"),
    "ts": ("TS", None),
    "ths": ("ThS", None),
    "ks": ("KS", None),
    "cn": ("CN", None),
    "dh": ("CN", None),  # "Đại học" ≈ Cử nhân
}


@dataclass(frozen=True)
class ExtractedRecord:
    full_name: str
    institutional_email: str | None
    academic_degree: str | None
    academic_rank: str | None
    position: str | None
    faculty: str | None
    department: str | None
    profile_url: str | None
    known_specialisation: str | None

    def as_dict(self) -> dict:
        return {
            "full_name": self.full_name,
            "institutional_email": self.institutional_email,
            "academic_degree": self.academic_degree,
            "academic_rank": self.academic_rank,
            "position": self.position,
            "faculty": self.faculty,
            "department": self.department,
            "profile_url": self.profile_url,
            "known_specialisation": self.known_specialisation,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_tags(fragment: str) -> str:
    text = _HTML_TAG_RE.sub(" ", fragment)
    return _WHITESPACE_RE.sub(" ", text).strip()


def _attr_value(tag_html: str, regex: re.Pattern[str], group: int = 1) -> str | None:
    match = regex.search(tag_html)
    if match is None:
        return None
    value = match.group(group).strip()
    return value or None


def _split_honorific_prefix(value: str) -> tuple[str | None, str | None]:
    """``"GS – TS"`` → ``("TS", "GS")`` / ``"PGS – TS"`` → ``("TS", "PGS")`` etc.

    The DSpace archive uses an en-dash (U+2013) between rank and degree.
    Falls back gracefully when the prefix is missing or does not follow
    the documented pattern. Returned ``academic_degree`` values use the
    canonical mixed-case vocabulary (TS, ThS, KS, CN) consumed by both
    the runtime parser and the validator.
    """
    if not value:
        return None, None
    cleaned = _WHITESPACE_RE.sub(" ", value.replace("\u2013", "-")).strip()
    tokens = [tok.strip(" .-") for tok in cleaned.split("-") if tok.strip(" .-")]
    if not tokens:
        return None, None
    last_upper = tokens[-1].upper()
    canonical_map = {"TS": "TS", "THS": "ThS", "KS": "KS", "CN": "CN", "DH": "CN"}
    degree: str | None = canonical_map.get(last_upper)
    rank: str | None = None
    if len(tokens) >= 2:
        first = tokens[0].upper()
        if first in {"PGS", "GS"}:
            rank = first
    return degree, rank


def _classify_from_data_attrs(
    data_rank: str | None, data_degree: str | None
) -> tuple[str | None, str | None]:
    degree_norm: str | None = None
    rank_norm: str | None = None
    if data_degree:
        mapping = _RANK_DEGREE_MAP.get(data_degree.strip().lower())
        if mapping is not None:
            degree_norm = mapping[0]
    if data_rank:
        mapping = _RANK_DEGREE_MAP.get(data_rank.strip().lower())
        if mapping is not None:
            rank_norm = mapping[1]
    return degree_norm, rank_norm


def _parse_card_body(tag_html: str, body_html: str) -> ExtractedRecord | None:
    data_name = _attr_value(tag_html, _ATTR_DATA_NAME_RE)
    data_rank = _attr_value(tag_html, _ATTR_DATA_RANK_RE)
    data_degree = _attr_value(tag_html, _ATTR_DATA_DEGREE_RE)
    data_position = _attr_value(tag_html, _ATTR_DATA_POSITION_RE)

    name_match = _NAME_ANCHOR_RE.search(body_html)
    if not name_match:
        return None
    full_name = _strip_tags(name_match.group("name"))
    if not full_name:
        return None

    profile_url: str | None = None
    href_match = _HREF_RE.search(name_match.group(0))
    if href_match:
        profile_url = href_match.group(1).strip()

    job_title: str | None = None
    prefix_value: str | None = None
    knows_about: str | None = None
    for m in _ITEMPROP_BODY_RE.finditer(body_html):
        key = m.group("key").lower()
        body = _strip_tags(m.group("body"))
        if key == "jobtitle":
            job_title = body or None
        elif key == "honorificprefix":
            prefix_value = body or None
        elif key == "knowsabout":
            knows_about = body or None

    email_value: str | None = None
    mailto_match = _EMAIL_MAILTO_RE.search(body_html)
    if mailto_match:
        email_value = mailto_match.group("email").strip().lower()
    if not email_value:
        fallback = _EMAIL_RE.search(body_html)
        if fallback:
            email_value = fallback.group(0).strip().lower()

    degree, rank = _split_honorific_prefix(prefix_value or "")
    fallback_degree, fallback_rank = _classify_from_data_attrs(data_rank, data_degree)
    degree = degree or fallback_degree
    rank = rank or fallback_rank

    position = (data_position or "").strip() or job_title

    return ExtractedRecord(
        full_name=full_name,
        institutional_email=email_value,
        academic_degree=degree,
        academic_rank=rank,
        position=position or None,
        faculty=None,
        department=None,
        profile_url=profile_url,
        known_specialisation=knows_about,
    )


def extract_records(html: str) -> list[ExtractedRecord]:
    """Parse the cached DSpace archive HTML into structured records."""
    records: list[ExtractedRecord] = []
    pos = 0
    while True:
        open_match = _ARTICLE_OPEN_RE.search(html, pos)
        if open_match is None:
            break
        close_match = _ARTICLE_CLOSE_RE.search(html, open_match.end())
        if close_match is None:
            break
        body = html[open_match.end() : close_match.start()]
        rec = _parse_card_body(open_match.group(0), body)
        if rec is not None:
            records.append(rec)
        pos = close_match.end()
    return records


def normalise_records(records: Iterable[ExtractedRecord]) -> list[dict]:
    """Drop empty rows, dedup by (name, profile_url), sort deterministically."""
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for rec in records:
        name_key = _WHITESPACE_RE.sub(" ", rec.full_name).casefold()
        url_key = (rec.profile_url or "").rstrip("/").casefold()
        dedup_key = (name_key, url_key)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        out.append(rec.as_dict())
    out.sort(
        key=lambda r: (
            (r["full_name"].casefold()),
            (r["profile_url"] or ""),
        )
    )
    return out
