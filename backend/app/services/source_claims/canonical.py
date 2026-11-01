"""Canonical JSON, hashing and value normalization for source claims.

Pure module: standard library only. ``canonical_json`` mirrors the settings of
``matching.candidate_persistence.canonical_json`` (sorted keys, compact
separators, UTF-8 without ASCII escaping) without importing that module,
which pulls in SQLAlchemy and the ORM models.

Two rules keep hashing honest:
- Hashes are computed over the raw source values. Normalization never feeds a
  content or record hash, so two raw values that normalize alike stay distinct.
- Only plain JSON values are accepted. Floats are rejected because their text
  form is not a stable identity for source data.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.services.source_claims.contract import Issue, NormalizedValue, Severity


class NonCanonicalValueError(ValueError):
    """The value cannot be represented as canonical source JSON."""


def _check(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        raise NonCanonicalValueError(f"float not allowed in source content at {path}")
    if isinstance(value, list):
        for index, item in enumerate(value):
            _check(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise NonCanonicalValueError(f"non-string key at {path}")
            _check(item, f"{path}.{key}")
        return
    raise NonCanonicalValueError(f"unsupported type {type(value).__name__} at {path}")


def canonical_json(value: Any) -> str:
    """Serialize plain JSON deterministically: object key order is irrelevant."""
    _check(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


# ---------------------------------------------------------------------------
# Normalizers. Each returns the raw value untouched next to the normalized one.
# ---------------------------------------------------------------------------

SCOPUS_ID_METHOD = "SCOPUS_ID_NFKC_TRIM_DIGITS_6_15_V1"
ORCID_METHOD = "ORCID_NFKC_TRIM_PREFIX_UPPER_CHECKSUM_V1"
EMAIL_METHOD = "EMAIL_NFKC_TRIM_CASEFOLD_V1"
NAME_METHOD = "NAME_NFKC_COLLAPSE_CASEFOLD_V1"
SOURCE_ID_METHOD = "SOURCE_ID_TRIM_URL_HOST_LOWER_NO_TRAILING_SLASH_V1"
COUNT_METHOD = "COUNT_NFKC_TRIM_NONNEGATIVE_INT_V1"

_SCOPUS_ID_RE = re.compile(r"^[0-9]{6,15}$")
_ORCID_RE = re.compile(r"^[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]$")
_ORCID_PREFIX_RE = re.compile(r"^(?:https?://)?(?:www\.)?orcid\.org/", re.IGNORECASE)
# Same practical shape as lecturer_dataset.parser.EMAIL_RE (not imported: that
# package's __init__ loads the ORM importer).
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_ID_LIST_SEPARATORS = re.compile(r"[\s,;/|]+")


def _issue(code: str, message: str, field: str | None, severity=Severity.ERROR) -> Issue:
    return Issue(code=code, severity=severity, message=message, field=field)


def _text(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (str, int)):
        return None
    return str(raw)


def normalize_scopus_id(raw: Any, field: str | None = None) -> NormalizedValue:
    text = _text(raw)
    if text is None:
        return NormalizedValue(None if raw is None else str(raw), None, SCOPUS_ID_METHOD, (
            _issue("SCOPUS_ID_MISSING" if raw is None else "SCOPUS_ID_NOT_TEXT",
                   "Scopus ID missing or not text.", field),))
    candidate = unicodedata.normalize("NFKC", text).strip()
    if not _SCOPUS_ID_RE.match(candidate):
        return NormalizedValue(text, None, SCOPUS_ID_METHOD, (
            _issue("SCOPUS_ID_INVALID", f"Not a 6-15 digit Scopus ID: {text!r}.", field),))
    return NormalizedValue(text, candidate, SCOPUS_ID_METHOD)


def _orcid_checksum_ok(orcid: str) -> bool:
    """ISO 7064 MOD 11-2 check digit, as specified by ORCID."""
    digits = orcid.replace("-", "")
    total = 0
    for char in digits[:-1]:
        total = (total + int(char)) * 2
    result = (12 - total % 11) % 11
    expected = "X" if result == 10 else str(result)
    return digits[-1] == expected


def normalize_orcid(raw: Any, field: str | None = None) -> NormalizedValue:
    text = _text(raw)
    if text is None or not text.strip():
        return NormalizedValue(text, None, ORCID_METHOD, (
            _issue("ORCID_MISSING", "ORCID empty or not text.", field, Severity.WARNING),))
    candidate = unicodedata.normalize("NFKC", text).strip()
    candidate = _ORCID_PREFIX_RE.sub("", candidate).upper()
    if not _ORCID_RE.match(candidate):
        return NormalizedValue(text, None, ORCID_METHOD, (
            _issue("ORCID_FORMAT_INVALID", f"Not an ORCID iD: {text!r}.", field),))
    if not _orcid_checksum_ok(candidate):
        return NormalizedValue(text, None, ORCID_METHOD, (
            _issue("ORCID_CHECKSUM_INVALID", f"ORCID check digit fails: {text!r}.", field),))
    return NormalizedValue(text, candidate, ORCID_METHOD)


def normalize_email(raw: Any, field: str | None = None) -> NormalizedValue:
    text = _text(raw)
    if text is None or not text.strip():
        return NormalizedValue(text, None, EMAIL_METHOD, (
            _issue("EMAIL_MISSING", "E-mail empty or not text.", field, Severity.WARNING),))
    candidate = unicodedata.normalize("NFKC", text).strip().casefold()
    if not _EMAIL_RE.match(candidate):
        return NormalizedValue(text, None, EMAIL_METHOD, (
            _issue("EMAIL_INVALID", f"Not an e-mail address: {text!r}.", field),))
    return NormalizedValue(text, candidate, EMAIL_METHOD)


def normalize_name(raw: Any, field: str | None = None) -> NormalizedValue:
    """Lookup signal only. A normalized name is never an identity key."""
    text = _text(raw)
    if text is None or not text.strip():
        return NormalizedValue(text, None, NAME_METHOD, (
            _issue("NAME_MISSING", "Name empty or not text.", field, Severity.WARNING),))
    collapsed = " ".join(unicodedata.normalize("NFKC", text).split())
    return NormalizedValue(text, collapsed.casefold(), NAME_METHOD)


def normalize_source_id(raw: Any, field: str | None = None) -> NormalizedValue:
    """Stable profile key. URLs: scheme/host lower-cased, default port, fragment and
    trailing slash removed; path and query are kept as published (they may be
    case-sensitive). Non-URL identifiers are only trimmed.

    A malformed HTTP(S) URL (invalid port, bad IPv6 authority, no host) returns
    ``normalized=None`` with a ``SOURCE_URL_MALFORMED`` issue so that the raw
    value is preserved and the caller can fall back to a weaker key. It is
    never silently accepted as a stable STRONG source key. IPv6 hosts are kept
    in brackets so the normalized URL parses back to the same host and port.
    """
    text = _text(raw)
    if text is None or not text.strip():
        return NormalizedValue(text, None, SOURCE_ID_METHOD, (
            _issue("SOURCE_ID_MISSING", "Profile source_id empty or not text.", field,
                   Severity.WARNING),))
    candidate = text.strip()
    if re.match(r"^https?://", candidate, re.IGNORECASE):
        try:
            parts = urlsplit(candidate)
            hostname = parts.hostname
            port = parts.port
        except ValueError:
            return NormalizedValue(text, None, SOURCE_ID_METHOD, (
                _issue("SOURCE_URL_MALFORMED",
                       f"Cannot parse URL authority or port: {text!r}.", field),))
        if not hostname:
            return NormalizedValue(text, None, SOURCE_ID_METHOD, (
                _issue("SOURCE_URL_MALFORMED", f"URL has no host: {text!r}.", field),))
        host = f"[{hostname}]" if ":" in hostname else hostname
        default = {"http": 80, "https": 443}.get(parts.scheme.lower())
        netloc = host if port in (None, default) else f"{host}:{port}"
        path = parts.path.rstrip("/") or "/"
        candidate = urlunsplit((parts.scheme.lower(), netloc, path, parts.query, ""))
    return NormalizedValue(text, candidate, SOURCE_ID_METHOD)


def parse_count(raw: Any, field: str | None = None) -> NormalizedValue:
    text = _text(raw)
    if text is None or not text.strip():
        return NormalizedValue(text, None, COUNT_METHOD, (
            _issue("COUNT_MISSING", "Declared count empty.", field, Severity.WARNING),))
    candidate = unicodedata.normalize("NFKC", text).strip()
    if not candidate.isdigit():
        return NormalizedValue(text, None, COUNT_METHOD, (
            _issue("COUNT_INVALID", f"Declared count is not a number: {text!r}.", field,
                   Severity.WARNING),))
    return NormalizedValue(text, str(int(candidate)), COUNT_METHOD)


def split_scopus_id_list(raw: Any) -> list[str]:
    """Split a source cell listing Scopus IDs. Tokens stay raw; validation is
    applied per token so one bad token never drops the others."""
    text = _text(raw)
    if text is None:
        return []
    return [token for token in _ID_LIST_SEPARATORS.split(text.strip()) if token]
