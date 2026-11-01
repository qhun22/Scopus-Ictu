# E3-P3-A — Source claims → matching and evidence bridge: handover for independent review

Date: 2026-10-29 · Status: **P3-A DELIVERED — STOPPED FOR INDEPENDENT REVIEW** (P3-B and P4 not
started)

Scope kept:
- a pure bridge, its DTOs and synthetic tests only;
- no database connection, migration, real data, endpoint, frontend, reviewer decision, commit or push;
- the matching engine, candidate persistence, review services, models and all accepted E3 code are
  unchanged (21/21 accepted files, and 7/7 matching, review and identity files byte-equal to HEAD).

## 1. Files (all new)

| File | Content |
|---|---|
| `backend/app/services/source_claim_matching/__init__.py` | package |
| `backend/app/services/source_claim_matching/bridge.py` | DTOs: `CaptureRef`, `ObservedClaim`, `LecturerRef`, `ScopusAuthorRef`, `DecisionRef`; `bridge_source_claims` (outputs `SourceClaimEvidence`, `PairAssessment`, `Finding`); `observations_from_snapshot` |
| `backend/tests/unit/test_source_claim_matching_bridge.py` | 27 synthetic tests |
| `docs/qa/gate_e3/E3P3A_MATCHING_MAPPING.md` | the verified interfaces, the evidence mapping and the blockers |

## 2. What was verified in the existing code

The facts are pinned in `E3P3A_MATCHING_MAPPING.md` §1:
- candidates are name-based pairs of `(lecturer_id, scopus_author_id)` UUIDs;
- publication evidence is a separate additive type;
- persistence re-observes roots without changing status;
- evidence kinds are limited to `NAME` and `PUBLICATION` by a CHECK;
- ACCEPT is the only path to an APPROVED identity, and it fails closed on unknown evidence kinds;
- the D-2 reason policy keys on `PUBLICATION`;
- the lecturer source id is the `repository_profile_url`, and lecturer e-mail is not unique;
- `scopus_authors` has no ORCID.

A test pins the evidence-kind CHECK, the promotion map and the D-2 trigger, so P3-B must change them
deliberately.

**Blocker (documented, not worked around):** the existing candidate evidence contract cannot store or
promote source-claim evidence. P3-A therefore delivers a **separate transient type**, the same pattern
as the existing `PublicationEvidence`, and makes no change to the matching engine. P3-B needs:
- a migration adding an evidence kind;
- an owner decision on ACCEPT promotion and on D-2;
- an owner decision on whether source-declared pairs create candidate roots.

See mapping §7.

## 3. Bridge behaviour

- **Evidence only from owned claims:** a `SCOPUS_ID_OWNED` claim whose subject resolves **by profile
  URL or e-mail** to exactly one lecturer, and whose Scopus ID is in the catalog, gives a
  `SourceClaimEvidence` with tier `INSTITUTION_DECLARED`, the primary/listed source flags,
  traceability and presence. **Never by name.**
- **Declared ORCIDs and e-mails:** consistency findings only. No pair evidence and no slot
  verification (R-13). ORCID collisions are flagged (R-14).
- **Unowned (ambiguous/unassigned) IDs:** findings, never pairs (R-15).
- **Findings for everything else:**
  - weak, unresolved, ambiguous or conflicting subjects;
  - invalid values;
  - catalog misses.
- **Classification:** `VERIFIED_ASSOCIATION` only when an APPROVED identity already exists. Otherwise
  `CONFLICTING_EVIDENCE`, `INSUFFICIENT_EVIDENCE` (all claims withdrawn) or `PLAUSIBLE_CANDIDATE`.
- **Every pair:** `accept_reason_required = True` (R-05), `decision_preserved = True`, and the stored
  statuses echoed. A negative prior decision is flagged `…REVIEWER_REOPEN_REQUIRED`.

## 4. Projection policy (stated in code and tests)

- **Fail-closed input contract:** one rule set, one analysis per capture, no duplicate observations,
  every capture known. This is exactly the `source_claim_observations` projection.
- **Claim identity:** `(source_system, scope_key, projection_version, claim_key)`.
- **Evidence key:** `(lecturer, author, rule id, rule version, source_system, scope_key, projection,
  claim_key)`; the fingerprint is the SHA-256 of that key.
- **Traceability:** repeated captures, artifact versions and re-analyses collapse onto one evidence
  item, with `observed_in` listing each observation (capture, analysis, contract version, claim,
  record).
- **Presence:** `CURRENT`, `NOT_OBSERVED` (including every PARTIAL case) or `WITHDRAWN` (only after a
  later COMPLETE capture). Withdrawal never revokes.

## 5. Tests

| # | Scenario | Test |
|---|---|---|
| 1 | one lecturer, several Scopus IDs (primary flag kept) | `test_1_…` |
| 2 | one Scopus ID in several source rows | `test_2_…` (both kept, CONFLICTING) |
| 3 | duplicate ORCID on distinct profiles | `test_3_…` (flagged, never evidence) |
| 4 | declared e-mail resolves the subject; names never do | `test_4_…`, `test_4b_…` |
| 5 | weak, ambiguous, unresolved and conflicting subjects | `test_5_…`, `test_5b_…` |
| 6 | conflicting claims (cross-table, approved elsewhere) | `test_6_…` |
| 7 | repeated identical capture: no inflation | `test_7_…` |
| 8 | several artifact versions for one capture | `test_8_…` (refused unless projected; same evidence) |
| 9 | new rule version: same evidence identity, mixing refused | `test_9_…` |
| 10 | PARTIAL never withdraws; COMPLETE withdraws without revoking | `test_10_…`, `test_10b_…` |
| 11 | ACCEPTED, REJECTED, REVOKED, SUPERSEDED and PENDING decisions echoed, never changed; R-16 | `test_11_…` (5 cases), `test_11b_…`, `test_11c_…` |
| 12 | invalid claim never evidence | `test_12_…` |
| 13 | deterministic under shuffled input | `test_13_…` |
| + | traceability; catalog misses and unowned IDs; refused inputs; pinned contract; purity | 5 tests |

**Results:**

| Check | Result |
|---|---|
| Bridge suite | 27 passed |
| Full offline suite (P1 + P2-A + B1 + provenance + B2 + P3-A) | **311 passed** (284 + 27) |
| Existing matching unit tests (unchanged files) | 37 passed. The 7 errors are `fixture 'isolated_db_engine' not found`: those PostgreSQL-backed tests need the project conftest and a test database, so they were not run |
| Ruff (all E3 code, fixtures and tests) | exit 0 |
| Ten-diff replay (P1 → … → B2 correction → P3-A), `--whitespace=error` | all OK; 3/3 files reproduce the workspace; reverse check OK |
| G01–G04 | 31/31 MATCH |
| `git status` | the same 17 tracked modifications; P3-A adds only untracked files |

**Mutation probes** (each safeguard disabled in memory):

| Safeguard removed | Tests failing |
|---|---|
| input validation | 3 |
| completeness check in withdrawal | 1 |
| claim de-duplication | 1 |
| negative-decision flag | 3 |

## 6. Decision protection

- The bridge reads `DecisionRef`s and only echoes them; no output field writes or proposes a status
  (tested).
- An APPROVED pair stays `VERIFIED_ASSOCIATION` even when the source withdraws the claim; this is
  reported as a finding.
- An ID APPROVED for another lecturer makes any other pair `CONFLICTING_EVIDENCE`, matching the review
  service's own refusal.
- Existing persistence already re-observes roots without changing status. Its PostgreSQL test
  (`test_new_run_reuses_rejected_root_without_reopening`) exists but was not run here.

## 7. Deferred to P3-B

The details are in `E3P3A_MATCHING_MAPPING.md` §7–8:
- a staging-row reader that maps database rows into the bridge DTOs;
- the evidence-kind migration and persistence;
- the ACCEPT, D-2 and candidate-root decisions;
- reviewer display;
- the PostgreSQL integration gate (staging migration, 4 B2 tests, G04, the candidate-persistence
  PostgreSQL tests).

**Owner decisions needed before P3-B:**
1. Does an ICTU source declaration create a candidate root when the name rules found none?
2. Is source-claim evidence promoted on ACCEPT, and to which `IdentityEvidence` type?
3. Should source-claim evidence lift D-2 `NAME_EVIDENCE_ONLY`? The recommendation is no.
4. Adopt the tier name `INSTITUTION_DECLARED`.

O-2 and O-7 are still to be formally confirmed.

STOPPED after P3-A.
