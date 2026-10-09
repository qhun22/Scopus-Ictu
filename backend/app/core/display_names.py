"""Repair of one KNOWN display-name corruption (Task 14).

The ADMIN label ``Quản trị viên`` was echoed as ``Qu?n tr? vi?n`` (non-ASCII
letters replaced by ``?``) by some clients/consoles.  Only that exact pattern,
or a name consisting solely of ``?`` and whitespace, is treated as corrupted;
any other name that legitimately contains ``?`` is returned unchanged.
"""

from __future__ import annotations

import re

ADMIN_LABEL = "Quản trị viên"
_CORRUPTED_ADMIN = re.compile(r"^qu\?n tr\? vi\?n$", re.IGNORECASE)
_ONLY_PLACEHOLDERS = re.compile(r"^[\s?]+$")


def is_corrupted_name(name: str | None) -> bool:
    if not name:
        return False
    trimmed = name.strip()
    return bool(_CORRUPTED_ADMIN.match(trimmed) or _ONLY_PLACEHOLDERS.match(trimmed))


def repair_display_name(name: str | None, role: str | None = None) -> str | None:
    """Return ``name`` unchanged unless it is the known corruption of the ADMIN label."""
    if not is_corrupted_name(name):
        return name
    if (role or "").upper() == "ADMIN" or _CORRUPTED_ADMIN.match((name or "").strip()):
        return ADMIN_LABEL
    return name
