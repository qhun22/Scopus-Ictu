"""Pure analyses over parsed source snapshots (Gate E.3 / P1).

Nothing here decides identity. Collisions and withdrawals are reported for a
human reviewer; no claim is attributed, merged, corrected or revoked.

Withdrawal rule: ``WITHDRAWN`` is reported only when both snapshots are
COMPLETE, cover the same scope (same source, URL and captured tables), and were
parsed under the same contract major, identity-rules and normalization
versions, in chronological order. Otherwise an absent item is ``NOT_OBSERVED``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.services.source_claims.contract import (
    SCOPUS_CLAIM_TYPES,
    ClaimItem,
    ClaimType,
    Completeness,
    KeyStrength,
    ParsedSnapshot,
    RecordKind,
)

# ---------------------------------------------------------------------------
# Collisions within one snapshot
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class DeclaredValueCollision:
    claim_type: str
    value: str                    # normalized value shared by the records
    record_refs: tuple[str, ...]
    raw_values: tuple[str, ...]   # distinct raw spellings, all preserved


def declared_value_collisions(
    snapshot: ParsedSnapshot, claim_type: ClaimType,
) -> tuple[DeclaredValueCollision, ...]:
    """Same normalized ORCID or e-mail declared by two or more distinct records.

    Every record keeps its own claim. Nothing is chosen or deduplicated.
    """
    if claim_type not in (ClaimType.ORCID_DECLARED, ClaimType.EMAIL_DECLARED):
        raise ValueError("only declared ORCID/e-mail claims are grouped")
    by_value: dict[str, list[ClaimItem]] = defaultdict(list)
    for claim in snapshot.claims:
        if claim.claim_type is claim_type and claim.value.valid:
            by_value[claim.value.normalized].append(claim)
    groups = []
    for value, claims in sorted(by_value.items()):
        refs = tuple(sorted({claim.record_ref for claim in claims}))
        if len(refs) > 1:
            raws = tuple(sorted({claim.value.raw for claim in claims if claim.value.raw}))
            groups.append(DeclaredValueCollision(claim_type.value, value, refs, raws))
    return tuple(groups)


def orcid_collision_groups(snapshot: ParsedSnapshot) -> tuple[DeclaredValueCollision, ...]:
    return declared_value_collisions(snapshot, ClaimType.ORCID_DECLARED)


class ScopusCollisionKind(StrEnum):
    CROSS_TABLE = "CROSS_TABLE"     # same ID in more than one claim category
    MULTI_OWNER = "MULTI_OWNER"     # same ID owned by more than one source row
    REPEATED_ROW = "REPEATED_ROW"   # same unowned ID listed in several rows


@dataclass(frozen=True, slots=True)
class ScopusCollision:
    scopus_id: str
    kinds: tuple[ScopusCollisionKind, ...]
    claim_types: tuple[str, ...]
    record_refs: tuple[str, ...]


def scopus_id_collisions(snapshot: ParsedSnapshot) -> tuple[ScopusCollision, ...]:
    by_id: dict[str, list[ClaimItem]] = defaultdict(list)
    for claim in snapshot.claims:
        if claim.claim_type in SCOPUS_CLAIM_TYPES and claim.value.valid:
            by_id[claim.value.normalized].append(claim)
    result = []
    for scopus_id, claims in sorted(by_id.items()):
        types = {claim.claim_type for claim in claims}
        refs = {claim.record_ref for claim in claims}
        kinds = []
        if len(types) > 1:
            kinds.append(ScopusCollisionKind.CROSS_TABLE)
        owners = {c.record_ref for c in claims if c.claim_type is ClaimType.SCOPUS_ID_OWNED}
        if len(owners) > 1:
            kinds.append(ScopusCollisionKind.MULTI_OWNER)
        unowned = [c for c in claims if c.claim_type is not ClaimType.SCOPUS_ID_OWNED]
        if len({c.record_ref for c in unowned}) > 1 and len(types) == 1:
            kinds.append(ScopusCollisionKind.REPEATED_ROW)
        if kinds:
            result.append(ScopusCollision(
                scopus_id, tuple(kinds), tuple(sorted(t.value for t in types)),
                tuple(sorted(refs)),
            ))
    return tuple(result)


def declared_vs_actual(snapshot: ParsedSnapshot) -> dict[str, dict[str, Any]]:
    """Source-declared counts next to the counted listing. Never corrected."""
    actual: dict[str, int] = defaultdict(int)
    names = {
        RecordKind.MULTI_ID_ROW: "MULTI_ID_LECTURERS",
        RecordKind.AMBIGUOUS_ID_ROW: "AMBIGUOUS_IDS",
        RecordKind.UNASSIGNED_ID_ROW: "UNASSIGNED_IDS",
        RecordKind.PROFILE: "PROFILES",
    }
    for record in snapshot.records:
        actual[names[record.record_kind]] += 1
    declared = dict(snapshot.declared_counts)
    return {
        key: {"declared": declared.get(key), "actual": actual.get(key, 0),
              "consistent": declared.get(key) in (None, actual.get(key, 0))}
        for key in sorted(set(declared) | set(actual))
    }


def distinct_scopus_ids(snapshot: ParsedSnapshot) -> dict[str, int]:
    """Distinct valid Scopus IDs per claim category and overall."""
    per_type: dict[str, set[str]] = defaultdict(set)
    for claim in snapshot.claims:
        if claim.claim_type in SCOPUS_CLAIM_TYPES and claim.value.valid:
            per_type[claim.claim_type.value].add(claim.value.normalized)
    overall = set().union(*per_type.values()) if per_type else set()
    return {**{key: len(value) for key, value in sorted(per_type.items())},
            "ALL": len(overall)}


# ---------------------------------------------------------------------------
# Presence between two snapshots
# ---------------------------------------------------------------------------

class PresenceStatus(StrEnum):
    NEW = "NEW"
    UNCHANGED = "UNCHANGED"
    CHANGED = "CHANGED"                    # same key, different content/value
    RECLASSIFIED = "RECLASSIFIED"          # Scopus ID moved between claim categories
    OWNER_CHANGED = "OWNER_CHANGED"        # owned ID now owned by another strong-keyed row
    OWNER_UNVERIFIABLE = "OWNER_UNVERIFIABLE"  # owner keys too weak to compare
    WITHDRAWN = "WITHDRAWN"                # absent from a comparable COMPLETE snapshot
    NOT_OBSERVED = "NOT_OBSERVED"          # absent, but absence proves nothing
    KEY_COLLISION = "KEY_COLLISION"        # key duplicated in either snapshot
    KEY_UNSTABLE = "KEY_UNSTABLE"          # content-derived key: absence is not removal


@dataclass(frozen=True, slots=True)
class PresenceEntry:
    dimension: str
    key: str
    status: PresenceStatus
    before: tuple[str, ...]
    after: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PresenceReport:
    comparable: bool
    reasons: tuple[str, ...]
    entries: tuple[PresenceEntry, ...]

    def by_status(self, status: PresenceStatus) -> tuple[PresenceEntry, ...]:
        return tuple(entry for entry in self.entries if entry.status is status)


def _moment(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def comparability(
    previous: ParsedSnapshot, current: ParsedSnapshot,
) -> tuple[bool, tuple[str, ...]]:
    if previous.source_system is not current.source_system:
        raise ValueError("snapshots of different source systems are never compared")
    reasons = []
    if previous.completeness is not Completeness.COMPLETE:
        reasons.append("PREVIOUS_NOT_COMPLETE")
    if current.completeness is not Completeness.COMPLETE:
        reasons.append("CURRENT_NOT_COMPLETE")
    if previous.scope_key != current.scope_key:
        reasons.append("SCOPE_DIFFERS")
    if previous.contract_version.split(".")[0] != current.contract_version.split(".")[0]:
        reasons.append("CONTRACT_MAJOR_DIFFERS")
    if previous.identity_rules_version != current.identity_rules_version:
        reasons.append("IDENTITY_RULES_DIFFER")
    if previous.normalization_version != current.normalization_version:
        reasons.append("NORMALIZATION_DIFFERS")
    if _moment(previous.capture.captured_at) > _moment(current.capture.captured_at):
        reasons.append("OUT_OF_ORDER")
    return not reasons, tuple(reasons)


def _absent_status(comparable: bool, strength: KeyStrength | None) -> PresenceStatus:
    if not comparable:
        return PresenceStatus.NOT_OBSERVED
    if strength is KeyStrength.WEAK:
        return PresenceStatus.KEY_UNSTABLE
    return PresenceStatus.WITHDRAWN


def _record_index(snapshot: ParsedSnapshot, kind: RecordKind):
    index: dict[str, list] = defaultdict(list)
    for record in snapshot.records:
        if record.record_kind is kind:
            index[record.record_key.value].append(record)
    return index


def _record_entries(previous, current, comparable) -> list[PresenceEntry]:
    entries = []
    for kind in (RecordKind.PROFILE, RecordKind.MULTI_ID_ROW):
        before, after = _record_index(previous, kind), _record_index(current, kind)
        for key in sorted(set(before) | set(after)):
            old, new = before.get(key, []), after.get(key, [])
            old_hashes = tuple(sorted(r.record_hash for r in old))
            new_hashes = tuple(sorted(r.record_hash for r in new))
            strength = (old or new)[0].record_key.strength
            if len(old) > 1 or len(new) > 1:
                status = PresenceStatus.KEY_COLLISION
            elif not old:
                status = PresenceStatus.NEW
            elif not new:
                status = _absent_status(comparable, strength)
            elif old_hashes == new_hashes:
                status = PresenceStatus.UNCHANGED
            else:
                status = PresenceStatus.CHANGED
            entries.append(PresenceEntry(f"RECORD:{kind.value}", key, status,
                                         old_hashes, new_hashes))
    return entries


def _scopus_states(snapshot: ParsedSnapshot) -> dict[str, list[ClaimItem]]:
    states: dict[str, list[ClaimItem]] = defaultdict(list)
    for claim in snapshot.claims:
        if claim.claim_type in SCOPUS_CLAIM_TYPES:
            value_key = claim.claim_key.rsplit("|", 1)[1]
            states[value_key].append(claim)
    return states


def _state_label(claim: ClaimItem) -> str:
    if claim.claim_type is ClaimType.SCOPUS_ID_OWNED:
        return f"{claim.claim_type.value}:{claim.subject_key}"
    return claim.claim_type.value


def _scopus_entries(previous, current, comparable) -> list[PresenceEntry]:
    entries = []
    before, after = _scopus_states(previous), _scopus_states(current)
    for scopus_key in sorted(set(before) | set(after)):
        old, new = before.get(scopus_key, []), after.get(scopus_key, [])
        old_labels = tuple(sorted({_state_label(c) for c in old}))
        new_labels = tuple(sorted({_state_label(c) for c in new}))
        if not old:
            status = PresenceStatus.NEW
        elif not new:
            # A Scopus ID key is the ID itself, never content-derived.
            status = _absent_status(comparable, KeyStrength.STRONG)
        elif old_labels == new_labels:
            status = PresenceStatus.UNCHANGED
        else:
            old_types = {c.claim_type for c in old}
            new_types = {c.claim_type for c in new}
            if old_types != new_types:
                status = PresenceStatus.RECLASSIFIED
            else:
                strengths = {c.flag("subject_key_strength") for c in old + new}
                weak = KeyStrength.WEAK.value in strengths
                status = (PresenceStatus.OWNER_UNVERIFIABLE if weak
                          else PresenceStatus.OWNER_CHANGED)
        entries.append(PresenceEntry("SCOPUS_ID", scopus_key, status, old_labels, new_labels))
    return entries


def _declared_index(snapshot: ParsedSnapshot, claim_type: ClaimType):
    values: dict[str, set[str]] = defaultdict(set)
    records: dict[str, set[str]] = defaultdict(set)
    strength: dict[str, str] = {}
    for claim in snapshot.claims:
        if claim.claim_type is claim_type:
            subject = claim.subject_key or "-"
            values[subject].add(claim.claim_key.rsplit("|", 1)[1])
            records[subject].add(claim.record_ref)
            strength[subject] = claim.flag("subject_key_strength")
    return values, records, strength


def _declared_entries(previous, current, comparable) -> list[PresenceEntry]:
    entries = []
    for claim_type in (ClaimType.ORCID_DECLARED, ClaimType.EMAIL_DECLARED):
        old_values, old_records, old_strength = _declared_index(previous, claim_type)
        new_values, new_records, _ = _declared_index(current, claim_type)
        for subject in sorted(set(old_values) | set(new_values)):
            old = tuple(sorted(old_values.get(subject, ())))
            new = tuple(sorted(new_values.get(subject, ())))
            if len(old_records.get(subject, ())) > 1 or len(new_records.get(subject, ())) > 1:
                status = PresenceStatus.KEY_COLLISION
            elif not old:
                status = PresenceStatus.NEW
            elif not new:
                raw_strength = old_strength.get(subject)
                status = _absent_status(
                    comparable, KeyStrength(raw_strength) if raw_strength else None)
            elif old == new:
                status = PresenceStatus.UNCHANGED
            else:
                status = PresenceStatus.CHANGED
            entries.append(PresenceEntry(claim_type.value, subject, status, old, new))
    return entries


def presence_diff(previous: ParsedSnapshot, current: ParsedSnapshot) -> PresenceReport:
    """Compare two snapshots of one source system. History is not modified."""
    comparable, reasons = comparability(previous, current)
    entries = (_record_entries(previous, current, comparable)
               + _scopus_entries(previous, current, comparable)
               + _declared_entries(previous, current, comparable))
    return PresenceReport(comparable, reasons, tuple(entries))
