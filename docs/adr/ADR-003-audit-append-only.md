# ADR-003 — Append-Only Audit

Status: ACCEPTED (Architecture v1.1)

## Context

Identity mappings between lecturers and Scopus authors are high-impact
governance data. Mistakes must be:

- traceable (who, when, why),
- reversible without loss of context,
- auditable across the lifetime of the system.

## Decision

The audit subsystem is **append-only**.

- `audit_events` rows are inserted and never updated or deleted.
- Undo / revert produces **compensating revisions** (new audit events
  describing the compensating action), never destructive history edits.
- The audit service is the single writer for `audit_events`.

## Consequences

- All destructive-looking operations become insert-only mutations plus
  audit events.
- The history of any mapping is reconstructable end-to-end.
- Storing PII in audit payloads must be minimized by the calling code.

## Prohibited

- `UPDATE` or `DELETE` against `audit_events` from any service or repo.
- "Silent" mutations that do not emit an audit event.
- Treating audit events as a general-purpose log.