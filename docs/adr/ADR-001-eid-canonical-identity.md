# ADR-001 — EID as Canonical Publication Identity

Status: ACCEPTED (Architecture v1.1)

## Context

Raw Scopus records may reappear across multiple CSV imports. Without a stable
canonical identity, the import pipeline cannot:

- deduplicate the same publication ingested twice,
- maintain consistent provenance across imports,
- guarantee that "publication X" means the same thing across services.

Publication name (canonical) candidates considered:

- DOI — not all Scopus rows have a DOI.
- Title — unstable; case, punctuation, accents vary across exports.
- Author + Title composite — fragile to author-name variants.
- **EID** — Scopus-internal stable identifier, present on every Scopus
  record row, unique per Scopus publication.

## Decision

The canonical publication external identity is **EID** (Scopus EID).

- `publications.eid` is the canonical identifier.
- DOI, when present, is stored as auxiliary evidence, not identity.
- Provenance of a canonical publication is maintained via
  `publication_raw_sources` (the join between a canonical publication and
  every raw record row that produced it).

## Consequences

- Multiple raw rows pointing to the same EID collapse into one canonical
  publication.
- Imports become reproducible: re-importing the same CSV is idempotent.
- EID must always be normalized to a canonical form (see M1 normalization
  spec).

## Prohibited

- Using DOI as the canonical identity.
- Using title as the canonical identity.
- Deleting `publication_raw_sources` history.