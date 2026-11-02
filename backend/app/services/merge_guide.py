"""ICTU "Scopus account merge guide": a hint for reviewing lecturers that hold several IDs.

The repository publishes the lecturers who have two or more Scopus Author IDs together with the
ID they currently use. The operator saves that table as a JSON file on the server; this module only
READS it. The file path comes from server settings (never from a request), a lecturer is matched by
institutional e-mail only (never by name), and the result is a hint: it pre-fills a review form but
confirms nothing. Without the file every function reports "not available" and nothing else changes.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.master_lecturer import Lecturer

_DEFAULT_RELATIVE = Path("data") / "lecturers" / "raw" / "merge_guide.json"
_SCOPUS_ID = re.compile(r"^\d{8,12}$")


@dataclass(frozen=True, slots=True)
class GuideEntry:
    email: str
    scopus_ids: tuple[str, ...]
    primary_scopus_id: str | None


@dataclass(frozen=True, slots=True)
class MergeGuide:
    source_url: str | None
    retrieved_at: str | None
    entries: dict[str, GuideEntry]  # keyed by lower-cased e-mail


@dataclass(frozen=True, slots=True)
class LecturerGuide:
    lecturer_id: uuid.UUID
    scopus_ids: tuple[str, ...]
    primary_scopus_id: str | None


def _guide_path() -> Path:
    configured = getattr(settings, "merge_guide_file", None)
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / _DEFAULT_RELATIVE


@lru_cache(maxsize=4)
def _load(path_text: str, mtime_ns: int) -> MergeGuide:
    del mtime_ns  # part of the cache key only: a changed file is re-read
    payload = json.loads(Path(path_text).read_text(encoding="utf-8"))
    entries: dict[str, GuideEntry] = {}
    for raw in payload.get("entries", []):
        email = str(raw.get("email", "")).strip().lower()
        ids = tuple(i for i in map(str, raw.get("scopus_ids", [])) if _SCOPUS_ID.match(i))
        if not email or not ids:
            continue
        primary = raw.get("primary_scopus_id")
        chosen = str(primary) if primary and str(primary) in ids else None
        entries[email] = GuideEntry(email, ids, chosen)
    return MergeGuide(payload.get("source_url"), payload.get("retrieved_at"), entries)


def load_merge_guide() -> MergeGuide | None:
    """The guide, or None when no file is present or it cannot be read."""

    path = _guide_path()
    try:
        return _load(str(path), path.stat().st_mtime_ns)
    except (OSError, ValueError):
        return None


def guides_for_lecturers(
    db: Session, guide: MergeGuide, lecturer_ids: set[uuid.UUID]
) -> list[LecturerGuide]:
    """The guide entry of each listed lecturer, matched by institutional e-mail only."""

    if not lecturer_ids:
        return []
    rows = db.execute(
        select(Lecturer.id, Lecturer.email).where(Lecturer.id.in_(lecturer_ids))
    ).all()
    found: list[LecturerGuide] = []
    for lecturer_id, email in rows:
        entry = guide.entries.get((email or "").strip().lower())
        if entry is not None:
            found.append(LecturerGuide(lecturer_id, entry.scopus_ids, entry.primary_scopus_id))
    return found
