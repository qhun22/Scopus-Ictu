# E3-P3-A — Source claims ↔ matching, evidence and review: verified mapping

Date: 2026-10-29. Everything in §1 was read from the repository code; nothing was assumed.

## 1. Existing interfaces (verified)

| Area | Code | Fact that constrains the bridge |
|---|---|---|
| Candidate (transient) | `services/matching/candidate_types.py` | `LecturerScopusCandidate(lecturer_id, scopus_author_id, scopus_id, preferred_name, evidence: CandidateEvidence…)`. `CandidateEvidence` is **name-only** (7 `RuleId` literals). Publication evidence is a *separate* additive type, `PublicationEvidence`, joined in `EnrichedLecturerScopusCandidate`. |
| Candidate generation | `matching/candidate_generator.py` | Read-only. It joins `lecturers.full_name` with Scopus name surfaces through 7 normalization rules, producing pairs keyed by the UUIDs `(lecturer_id, scopus_author_id)`. |
| Candidate persistence | `matching/candidate_persistence.py`, `models/candidate.py` | A root is unique per `(lecturer_id, scopus_author_id)`, and re-observing it only updates `last_seen_at`; it **never changes `status`**. Each generation run gets one observation per root (`observation_hash`). Evidence rows carry `evidence_kind CHECK IN ('NAME','PUBLICATION')`, rule id/version, payload, `source_refs` and a fingerprint. |
| Candidate status and review | `models/candidate.py`, `candidate_review_service.py` | Statuses `PENDING`, `ACCEPTED`, `REJECTED`, `SUPERSEDED`; reviews `ACCEPT`, `REJECT`, `REOPEN`. ACCEPT is the **only** path that creates `LecturerScopusIdentity(status='APPROVED')`. It refuses (`SCOPUS_AUTHOR_ALREADY_APPROVED_FOR_OTHER_LECTURER`) when the author is already APPROVED for another lecturer. |
| Evidence promotion on ACCEPT | `candidate_review_service._promote_candidate_evidence_to_identity` | Maps `NAME` to `NAME_SIMILARITY` and `PUBLICATION` to `DOI_EXACT`/`PUBLICATION_OVERLAP`. Any other kind raises `EvidencePromotionUnsupportedError` (fail closed). |
| Identity | `models/identity.py` | Statuses `CANDIDATE`, `APPROVED`, `REJECTED`, `REVOKED`; mapping reviews `APPROVE`, `REJECT`, `REVOKE`, `REOPEN`. `IdentityEvidence.evidence_type ∈ {APPROVED_ID, ORCID_EXACT, DOI_EXACT, PUBLICATION_OVERLAP, COAUTHOR_CONFIRMED, NAME_SIMILARITY, AFFILIATION_MATCH}`. One APPROVED lecturer per Scopus author (partial unique index). |
| D-2 reason policy | `review_reason_policy.py` | An ACCEPT needs a reason when there is no `PUBLICATION` evidence (`NAME_EVIDENCE_ONLY`), or when the author or the lecturer has several active candidates. |
| Lecturer keys | `models/master_lecturer.py`, `lecturer_dataset/importer.py` | `repository_profile_url` is the import's source id, matched as an **exact** string. `email` has a case-insensitive, **non-unique** index. `orcid` is unique when present. Known-publication ingestion refuses duplicate profile URLs. |
| Scopus author | `models/publication.py` | `scopus_authors(id, scopus_id UNIQUE, preferred_name)`; **no ORCID** column. |
| Staging (accepted P2) | `models/source_staging.py`, `services/source_staging/service.py` | `source_claim_observations` gives one analysis per capture under the active rule set; claims are never unique on `claim_key` alone. |

## 2. What each source claim can provide

| Claim | Lecturer ↔ Scopus association | Resolves the subject | Other signal | Never |
|---|---|---|---|---|
| `SCOPUS_ID_OWNED` (multi-ID rows) | **yes:** a declared association, *evidence* (`SOURCE_TIER = INSTITUTION_DECLARED`); primary/listed flags kept as source claims (R-06) | through the row's e-mail (`RESOLVED_EMAIL`) | a shared ID across rows → conflict | approval; name join |
| `SCOPUS_ID_AMBIGUOUS` / `SCOPUS_ID_UNASSIGNED` | **no** (no subject) | — | `UNOWNED_SCOPUS_ID_LISTED` (R-15 grouping input); cross-table conflict with owned claims | attribution |
| `EMAIL_DECLARED` | no | the record's e-mail is a subject key (MEDIUM) | `EMAIL_DECLARED_DIFFERS_FROM_LECTURER` when the profile resolves by URL | identity proof |
| `ORCID_DECLARED` (profiles) | **no.** `scopus_authors` has no ORCID, and R-13 allows only T1 (a publisher ORCID at the slot, confirmed by the registry) to verify | not used (R-14 collisions) | `ORCID_DECLARED_MATCHES_LECTURER` / `…_DIFFERS…` / `…_LECTURER_HAS_NONE` / `…_BY_MULTIPLE_RECORDS` | verified authorship |
| Name (`full_name`) | no | **never** (R-07, R-17) | — | any join |
| Publication corroboration | not in source claims; stays with the existing `PublicationEvidence` enricher | — | — | — |

## 3. Subject resolution (record → lecturer), conservative

Implemented in `_resolve`:
1. **WEAK** (content-keyed) record: `WEAK_SOURCE_KEY`, never resolved.
2. **Profile URL:** the normalized source id equals one lecturer's normalized `repository_profile_url`,
   giving `RESOLVED_SOURCE_ID`.
   - Several lecturers with that URL: `AMBIGUOUS`.
   - The record's e-mail resolves to a *different* lecturer: `CONFLICT`.
3. **E-mail:** otherwise, the normalized e-mail equals exactly one lecturer's e-mail, giving
   `RESOLVED_EMAIL`. Several matches: `AMBIGUOUS`.
4. **Otherwise** `UNRESOLVED`. No lecturer id is manufactured, and a finding `SUBJECT_<status>` is
   emitted.

## 4. Pair classification (`PairAssessment`)

| Class | Condition (first match wins) |
|---|---|
| `VERIFIED_ASSOCIATION` | an `APPROVED` identity already exists for the pair. Verification is a **reviewer** outcome; the bridge only echoes it, even when the source later withdraws the claim (finding `SOURCE_NO_LONGER_LISTS_APPROVED_ID`). |
| `CONFLICTING_EVIDENCE` | the author is APPROVED for another lecturer, **or** the ID is declared for several resolved lecturers, **or** the ID is also listed as AMBIGUOUS/UNASSIGNED in a current capture |
| `INSUFFICIENT_EVIDENCE` | every supporting claim was withdrawn from a later COMPLETE capture |
| `PLAUSIBLE_CANDIDATE` | otherwise |

Fields kept on every pair:
- `accept_reason_required = True`: a source listing alone never auto-accepts (R-05; consistent with the
  D-2 `NAME_EVIDENCE_ONLY` trigger, because source evidence is not `PUBLICATION`).
- `decision_preserved = True`; the existing candidate and identity statuses are echoed.
- A REJECTED or SUPERSEDED candidate, or a REJECTED or REVOKED identity, adds
  `PRIOR_NEGATIVE_DECISION_REVIEWER_REOPEN_REQUIRED`. Only a reviewer REOPEN can change it.
- **No output field writes or proposes a status.**

Findings outside pairs: invalid values, unowned IDs, IDs missing from the catalog (R-15), unresolved,
ambiguous, conflicting or weak subjects, and ORCID and e-mail consistency.

## 5. Projection policy (no evidence inflation)

- **Input contract, enforced:** exactly one rule set (`MIXED_RULE_VERSIONS`), one analysis per capture
  (`MULTIPLE_ANALYSES_PER_CAPTURE`), no duplicate (capture, claim) (`DUPLICATE_OBSERVATION`), and every
  capture known (`UNKNOWN_CAPTURE`). This is exactly what `source_claim_observations` delivers, so
  re-analysis and several artifact versions cannot double count.
- **Real-world claim identity:** `(source_system, scope_key, projection_version, claim_key)`.
  - Repeated captures, artifact versions and analyses of one claim collapse onto it.
  - Different sources or scopes stay separate evidence.
  - `claim_key` embeds the subject record key, so two different lecturers never merge.
- **Evidence key:** `(lecturer_id, scopus_author_id, BRIDGE_RULE_ID, BRIDGE_RULE_VERSION, source_system,
  scope_key, projection_version, claim_key)`; `fingerprint = sha256(canonical_json(key))`.
  - The fingerprint is stable across captures and source-rule re-analysis.
  - `observed_in` lists every (capture, analysis, artifact version, claim, record) for traceability.
- **Presence**, P1 semantics:
  - `CURRENT`: listed in the latest capture of the same scope and projection;
  - `WITHDRAWN`: absent from a later COMPLETE capture after a COMPLETE capture that listed it, with a
    non-weak key;
  - otherwise `NOT_OBSERVED`. PARTIAL never withdraws.

  Withdrawal never revokes or changes anything.

## 6. Research requirements covered

| R | How |
|---|---|
| R-05 | the source listing is its own evidence tier; `accept_reason_required` |
| R-06 | `is_primary_claimed` kept as a source flag, never computed |
| R-12 | missing (`NOT_OBSERVED`, `INSUFFICIENT_EVIDENCE`) is distinct from contradicting (`CONFLICTING_EVIDENCE`) |
| R-13 | declared ORCIDs give consistency findings only; nothing is slot-verified |
| R-14 | ORCID collisions are flagged, every claim is kept, nothing is picked |
| R-15 | unowned IDs and catalog misses are findings, not dropped |
| R-16 | lecturers with APPROVED IDs remain eligible for new plausible pairs (tested) |

## 7. Architectural blockers for persisting this in P3-B (no change made in P3-A)

1. **`lecturer_scopus_candidate_evidence.evidence_kind`** is limited to `NAME` and `PUBLICATION` by a
   CHECK. Persisting source-claim evidence needs a migration adding a kind, e.g. `SOURCE_CLAIM`.
2. **ACCEPT promotion fails closed** on unknown kinds (`EvidencePromotionUnsupportedError`). P3-B must
   either:
   - map `SOURCE_CLAIM` to an existing `IdentityEvidence` type (none fits exactly: `APPROVED_ID` would
     overstate a declaration), **or**
   - keep source-claim evidence in the review `evidence_snapshot` only.

   **Owner decision required.**
3. **D-2:** decide whether source-claim evidence counts toward "not name-only". The recommendation is
   **no**: keep the reason required (R-05).
4. **Candidate generation is name-based.** A source-declared pair that the name rules did not produce
   needs either a candidate root created by a source-claim generation run (same root table, new
   rule-set id) or reviewer-visible findings only. **Owner decision.**
5. **Source tier vocabulary:** R-02 lists PUBLISHER, REGISTRY, AGGREGATOR_RAW and AGGREGATOR_ENTITY;
   `INSTITUTION_DECLARED` is a proposed addition.

## 8. Deferred to P3-B

- A DB reader mapping staging rows (`source_claim_observations` + `source_records.normalized` +
  `source_captures`) and `lecturers`, `scopus_authors`, candidates and identities into the bridge DTOs.
- The migration and the persistence of source-claim evidence (§7.1).
- The ACCEPT and D-2 integration (§7.2–3), candidate regeneration (§7.4) and reviewer display.
- The PostgreSQL gate: the staging migration, the 4 B2 tests, the G04 tests, plus the existing
  `test_candidate_persistence.py` PostgreSQL tests (e.g.
  `test_new_run_reuses_rejected_root_without_reopening`).
