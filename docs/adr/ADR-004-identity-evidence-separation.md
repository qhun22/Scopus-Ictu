# ADR-004 — Identity and Evidence Separation

Status: ACCEPTED (Architecture v1.1)

## Context

A lecturer ↔ Scopus author mapping is the system's ground truth, but it is
constructed from many heterogeneous signals: approved Scopus IDs, ORCID,
DOI / publication overlap, name + co-author evidence, and fuzzy name
matches.

Conflating the mapping decision with the supporting evidence prevents:

- explaining *why* a mapping was approved,
- re-scoring candidates after a rule change,
- preserving evidence across compensating revisions.

## Decision

**Identity and evidence are separate concepts**, in separate tables.

- `lecturer_scopus_identities` holds the mapping decision (one row per
  approved identity link).
- `identity_evidence` holds the supporting evidence rows attached to a
  mapping or to a candidate.

## Evidence Strength Order (canonical)

1. Approved Scopus ID
2. ORCID exact match
3. DOI / publication overlap
4. Name + confirmed co-author evidence
5. Fuzzy name match

The strength order is a canonical ordering, not a numeric scoring rule.
Weights and thresholds are deferred to the matching rules ADR series.

## Consequences

- Reviewers can audit a mapping by reading its evidence rows.
- Re-running matching produces new evidence rows without rewriting the
  identity decision.
- Fuzzy-name evidence must never be the sole evidence for an identity;
  review must explicitly confirm.

## Prohibited

- Storing evidence inline on the identity row.
- Auto-approving a mapping based on fuzzy-name evidence alone.