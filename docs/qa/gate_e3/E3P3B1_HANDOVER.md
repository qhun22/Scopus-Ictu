# E3-P3-B1 — SOURCE_CLAIM candidate evidence

Date: 2026-10-30, Asia/Bangkok. Status: IMPLEMENTED OFFLINE; READY FOR INDEPENDENT REVIEW.
Live reviewer release: INACTIVE, blocked on E3-P3-B2. PostgreSQL: NOT_EXECUTED.

## Result and exact scope

Institutional declarations can now be stored explicitly as candidate evidence,
without name matching, identity verification or a reviewer decision. New roots
are PENDING only when a currently usable declaration resolves uniquely through
the accepted bridge to a local Scopus author. Existing candidate reviewer states
and canonical identities are never updated.

Six application/migration/test paths changed:

| Path | Change |
| --- | --- |
| `backend/app/models/candidate.py` | Add SOURCE_CLAIM vocabulary and STAGED run status/completion consistency. |
| `backend/app/services/matching/source_claim_candidate_persistence.py` | New dedicated writer and explicit offline CURRENT projection. |
| `backend/alembic/versions/b88f02d44ff2_source_claim_candidate_evidence.py` | New migration source, revising accepted `a77e01c33ee1`; changes three CHECKs only. |
| `backend/tests/unit/test_source_claim_candidate_persistence.py` | 39 synthetic SQLAlchemy/SQLite cases. |
| `backend/tests/unit/test_source_claim_matching_bridge.py` | Update only the storage-contract pin; promotion map and D-2 pins remain. |
| `backend/tests/unit/test_source_staging_schema.py` | Update only the expected migration head and assert the accepted staging revision is its parent. |

Five QA artifacts are delivered under `docs/qa/gate_e3/` with prefix E3P3B1.
No frontend, endpoint, reviewer handler, identity model, accepted staging service,
source parser/adapter or P3-A bridge implementation changed. No G01–G04 or Gate D
change. No commit, push, reset, clean, stash, application demo or real data import.

## Baseline and preservation

The authoritative baseline was the accepted, dirty pre-task worktree, captured
with `git status --short -uall`, branch and per-file SHA-256 before editing.
Branch: main. HEAD: `4bb69f6efaac945399b1c191fc12879ad1c62885` (context only).
The delivered diff is not a diff of all accepted E3 work against HEAD.

For existing changed files, the exact pre-task bytes were reconstructed from the
narrow edits and verified against their captured hashes before generating the
diff. The reverse patch check passes. The inventory covers tracked and non-ignored
untracked files, not ignored local datasets, credentials or complete filesystem trees.
Of 1,647 inventoried pre-existing files, only the three explicitly listed existing
files changed; 1,644 remain byte-identical. Existing accepted artifacts are preserved.

## Storage and eligibility

`SourceClaimCandidateWriter.persist_generation(run_id)` loads the active rule-set
selection, both staging views, retained source records/claims, the local catalog,
and existing reviewer states. It calls the accepted `bridge_source_claims`; it is
not another matching engine and takes no caller-supplied evidence payload.

- Evidence kind SOURCE_CLAIM, tier INSTITUTION_DECLARED. It is not NAME,
  PUBLICATION, ORCID_EXACT, DOI_EXACT or APPROVED_ID.
- One lecturer may retain several IDs; several lecturers may retain competing
  claims to one ID. Duplicate source ORCIDs remain separate source observations
  and collision findings, not ORCID_EXACT evidence or canonical ORCID updates.
- New roots require a CURRENT, valid, unambiguous declaration, an exact URL/email
  subject resolution and a Scopus ID already present in the catalog. No name
  fallback, author creation or identity action is performed.
- REJECTED/SUPERSEDED/ACCEPTED candidate roots receive observation history without
  any change to status, version or first/last-seen timestamps. A REJECTED/REVOKED
  identity prevents creation of a new candidate root for that pair. If a root
  already exists, it is retained; the negative decision remains in the snapshot.
- A pair without an eligible new root still retains all bridge findings and raw
  observation references in the generation's source_state. Invalid/unowned or
  catalog-missing claims are not converted into candidate identity evidence.

Logical fingerprints exclude capture, analysis, artifact/contract version, bridge
rule version and active-rule version. History still records those versions and
IDs on each observation. Historical evidence rows may repeat the same logical
fingerprint; they must never be counted as independent current weight.

## CURRENT versus history

The only implemented CURRENT read is the offline writer's `current_evidence()`.
It recomputes the accepted active projection and trusted representation, then
requires a fully verified STAGED run matching those exact current inputs. When
new captures, analyses, active rules or relevant decisions change the inputs,
the older run is stale: current output is empty until regeneration. It never
falls back to an inactive analysis or selects chronology by a run UUID.

Matching runs are validated and collapsed by logical fingerprint. Weight is a
binary usable-declaration indicator, not confidence in a person's identity:

| State | Current weight |
| --- | --- |
| CURRENT, valid and listed, no same-time ambiguity | 1 per logical declaration |
| WITHDRAWN after a provably later comparable COMPLETE capture | 0 |
| NOT_OBSERVED, including absence in PARTIAL captures | 0 |
| AMBIGUOUS, including contradictory same-time presence/flags | 0 |
| INVALID | 0 |

Same-time conflicting primary/listed flags are null in the normalized descriptor.
Capture chronology comes from the offset-aware timestamp in the immutable hashed
capture envelope; this also avoids SQLite DateTime losing the original offset.
All earlier immutable evidence rows, captures, analyses and raw records remain
traceable. An old evidence payload with weight 1 is history, not current authority.
The bridge's raw result is retained for diagnostics; its flags must not bypass the
normalized descriptor/current projection. See E3P3B1_EVIDENCE_MAPPING.md.

## Transaction ownership and replay

The caller owns the outer transaction. The writer flushes earlier pending caller
state before entering `begin_nested()`, then encloses preparation, run creation,
roots, observations, evidence and the STAGED transition in one SAVEPOINT.
It never commits, starts nested `Session.begin()` or calls full Session.rollback().
Unexpected integrity errors propagate after savepoint rollback. Pair uniqueness
uses ON CONFLICT with the explicit lecturer/author pair target; unrelated errors
are not swallowed. A failed run leaves no half-written writer records. Earlier
caller writes and earlier successful generations remain usable; retry is supported.
An invalid earlier pending caller write fails at the pre-savepoint flush and is
the caller's responsibility to recover.

An existing run UUID is replayed only when its rule set, STAGED lifecycle, full
source_state, expected pair membership, observation timestamp/hash/snapshot,
evidence kind/fingerprint/rules/payload and exact provenance all agree with the
trusted recomputation. Tampering is rejected, not repaired or accepted by hash
alone. Reusing a UUID after inputs change is rejected: use a new run UUID.
Persisted JSON values are detached copies, not aliases of prepared dictionaries.

## Reviewer compatibility release gate

No live caller is wired to this writer. SOURCE_CLAIM runs finish as STAGED, never
COMPLETED. Existing review queue/dashboard/current-observation queries select only
COMPLETED; a source-only root is not reviewable, and an existing completed NAME
observation remains current for the old reviewer flow. Tests exercise those queries.
Staged roots may increase ambiguity/reason counts for an existing reviewable pair;
they cannot waive D-2 or become publication support.

The serializer still treats non-NAME evidence as PUBLICATION, and ACCEPT has no
SOURCE_CLAIM promotion vocabulary in IdentityEvidence. These handlers are unchanged.
Do not manually promote STAGED runs to COMPLETED. P3-B2 must add an explicit
SOURCE_CLAIM serializer/snapshot, a current/history read contract, approved promotion
semantics, stale-observation validation and D-2 preservation before live release.
No P3-B2 code is included here.

## Validation actually performed

- Focused P3-B1: 39 passed. Final combined offline suite: **388 passed**, exit 0.
  This comprises 39 new P3-B1 cases, 327 existing E3 cases, and 22 existing pure
  matching/serialization cases. No final failures or skips.
- Real SQLAlchemy sessions against isolated SQLite in-memory mirrors and the
  existing offline synthetic fixtures; an existing suite case also uses its own
  temporary SQLite file. No PostgreSQL or application database was connected.
- Network connections and app.main/app.core.database/conftest initialization
  were blocked in the test launcher. Forbidden modules loaded: [].
- Initial draft: 29 pass / 4 fail (timezone/eligibility/version fixture issues).
  These were corrected; they are not a pre-feature regression demonstration.
- The first sandboxed full run hit Windows WinError 5 on pytest's temporary
  directory. The approved rerun and final run passed. Logs retain this limitation.
- Ruff 0.17.3: exit 0, no diagnostics across all six changed paths.
- Scoped diff check, added-line whitespace check and reverse patch check pass.
- Whole-worktree `git diff --check` is not clean: it reports trailing Markdown
  whitespace in the three pre-existing dirty `docs/research` files. Those files
  are byte-identical to the pre-task inventory and were not edited.
- `alembic heads` from backend reports `b88f02d44ff2 (head)`. This is metadata
  inspection only; no Alembic migration was executed. A wrong-cwd heads attempt
  failed harmlessly before the corrected read-only command.

## Deferred verification and limits

Migration source is authorized and delivered, but execution is NOT_EXECUTED.
Only evidence vocabulary and run-status CHECKs are changed. Downgrade fails closed
if SOURCE_CLAIM/STAGED rows exist; it does not delete history or make it reviewable.
Constraint parity was tested with recording fake Alembic operations, not a migration
environment or live schema.

SQLite mirror tests do not prove PostgreSQL JSONB/CHECK behavior, locking,
deadlocks, race recovery or deployment correctness. Its shared mirror omits PG
CHECKs/partial indexes; a separate real SQLite table executes the portable evidence
kind CHECK. No authorized disposable PostgreSQL target was used.

PostgreSQL follow-up must cover concurrent same-run/pair writers, retries under
actual isolation levels, coherent source/canonical input reads during ingestion,
rule activation and review, and full savepoint/caller rollback durability. No
whole-job concurrency guarantee or advisory-lock design is claimed. This feature
is offline and not released into live reviewer workflows while those checks and
P3-B2 compatibility are pending. Full input/provenance snapshots may be large;
production storage/query performance is unbenchmarked.

STOPPED after E3-P3-B1 for independent review. P3-B2 and P4 were not started.
