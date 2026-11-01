# E3-P3-B2-A — reviewer SOURCE_CLAIM read compatibility

Date: 2026-10-30 (Asia/Bangkok). Status: IMPLEMENTED OFFLINE; READY FOR REVIEW.
SOURCE_CLAIM reviewer decisions and workflow activation: NOT ENABLED.
PostgreSQL/HTTP integration: NOT_EXECUTED.

## Targeted correction B2A-R1 (2026-10-30)

Independent review reproduced stale-history timestamp/completeness tampering that
the first B2-A delivery accepted. `_historical_captures()` now verifies that
source_state is an object with a valid stored input_hash, recomputes the accepted
B1 canonical hash excluding only that field, and rejects missing/malformed or
mismatched hashes before reading capture metadata. Capture container/entries,
IDs, unique membership, timestamp type/offset and COMPLETE/PARTIAL values are
validated before use. Errors are SOURCE_CLAIM_EVIDENCE_INVALID; hashes/history
are never repaired, overwritten or silently skipped.

History validation now precedes the unchanged B1 CURRENT projection, so a malformed
historical state is rejected by this guard before reaching the B1 reader. This is
an offline provenance correction, not reviewer activation or a B1 writer change.
Service locations: `_historical_captures():127-167`, `_history():170-207`,
`source_claim_read_preview():210-288`.

R1 changes only `candidate_evidence_read.py`, its existing B2-A unit test file and
the five E3P3B2A artifacts. All original 37 B2-A test function bodies are unchanged;
28 new parametrized regression cases cover valid read-only history, both reported
tamper cases, missing/wrong hashes and malformed envelopes. Before code correction:
16 FAILED / 49 PASSED. After correction: 65 focused / 453 combined PASSED.

The correction baseline captured the dirty pre-fix worktree (1,662 listed files).
Only these seven existing paths changed; 1,655 others remain byte-identical. The
delivered IMPLEMENTATION.diff stays the cumulative four-path B2-A patch against
the original pre-B2-A worktree, with its API/schema sections byte-identical to the
reviewed patch. Validation separately records the two-file R1 before/after hashes
and correction-delta fingerprint. No new artifact or architecture was introduced.

## Outcome and change scope

The live detail serializer now dispatches NAME and PUBLICATION explicitly.
SOURCE_CLAIM is rejected with SOURCE_CLAIM_REVIEW_INACTIVE rather than becoming a
publication. Unknown kinds fail with CANDIDATE_EVIDENCE_KIND_UNSUPPORTED. Existing
NAME/PUBLICATION response fields and behavior are preserved.

A separate, unexposed `source_claim_read_preview(session, candidate_id)` supplies
an explicit SOURCE_CLAIM DTO for the future reviewer read contract. It reuses the
accepted P3-B1 CURRENT projection, labels historical/stale evidence, retains safe
trace IDs/versions and never forwards raw source dictionaries. It is not an HTTP
endpoint, authorization boundary, reviewer action or live release.

Exactly four code/test paths changed relative to the captured dirty worktree:

| Path | Change |
| --- | --- |
| `backend/app/api/v1/endpoints/reviews.py` | Replace only the detail serialization loop with explicit dispatch; two now-unused schema imports removed and the serializer imported. |
| `backend/app/schemas/review_api.py` | Add separate typed SOURCE_CLAIM trace/history/evidence/projection models and authority consistency validation. Existing response/request classes unchanged. |
| `backend/app/services/candidate_evidence_read.py` | New serializer and read-only, release-gated future source projection. |
| `backend/tests/unit/test_source_claim_reviewer_read.py` | 65 synthetic offline cases: 37 original plus 28 B2A-R1 regressions. |

Five E3P3B2A QA artifacts are delivered. No migration, model, accepted P1/P2/P3-A/
P3-B1 writer, G01–G04, reviewer business logic, frontend consumer, API route or
review queue query was added or rewritten. No commit/push/reset/clean/stash.

## Verified preflight and original B2-A baseline

Read the two independent P3-B1 acceptance notes: accepted/closed only at offline/
code scope, with PostgreSQL and live activation explicitly not authorized.
Inspected AGENTS.md/CLAUDE.md, reviewer schemas/queries/serializer, decision-time
snapshots, ACCEPT promotion, D-2, dashboard/context counts and frontend consumers.
Existing documentation's stale migration references were left untouched.

The cumulative patch baseline is the accepted original pre-B2-A worktree, not HEAD. Captured
`git status --short -uall`, branch, HEAD, exact relevant source text and SHA-256 of
1,655 Git-listed tracked/non-ignored-untracked existing files before editing.
Branch main; HEAD `4bb69f6efaac945399b1c191fc12879ad1c62885` is context only.
Only the two listed existing files changed; 1,653 remain byte-identical.

Before bytes for the delivered patch were reconstructed from the narrow edits
and checked against the captured SHA-256, including original CRLF line endings.
The patch contains only four task paths and reverse preflight passes. No previous
accepted diff was rewritten. Full filesystem/ignored-data preservation is not
claimed by the Git-listed subset inventory.

## Implemented read contract

`ReviewSourceClaimProjectionResponse` has reviewer_active=false,
decision_enabled=false and the unchanged E3-P3-B2_REQUIRED release gate. Each item
is one logical fingerprint with SOURCE_CLAIM / INSTITUTION_DECLARED, not an
identity approval tier. It contains:

- selection status ACTIVE_PROJECTION or HISTORICAL_ONLY;
- current state CURRENT/WITHDRAWN/NOT_OBSERVED/AMBIGUOUS/INVALID, or STALE when
  no verified current generation matches the active inputs;
- binary usable-declaration weight; current primary/listed flags only for CURRENT;
- historical states, recorded subject-resolution methods and allowlisted recorded
  conflict codes, explicitly historical rather than newly asserted current facts;
- per-evidence observation/run/rule-version history and deduplicated trace IDs,
  capture timestamps/completeness and analysis/contract/normalization versions;
- per-trace ACTIVE_PROJECTION/HISTORICAL_ONLY labels to distinguish old analyses
  and contract versions. Active provenance selection does not imply usable weight.

The reader obtains current authority only from the accepted writer's public
`current_evidence()` method. New captures, rules or relevant decisions stale the
old generation; history does not supply a fallback current claim. Historical
membership, snapshot/hash, full source_state input_hash, typed capture metadata,
pair identity, descriptor, logical fingerprint and run source references are checked
before rendering. Invalid data fails closed.
Repeated captures, generations, artifact versions and reanalysis produce history
without multiplying current logical items or weight.

Whitelist serialization deliberately excludes raw row content/issues, claim and
record keys, subject keys, e-mails, ORCID context, raw flags, arbitrary payloads,
source URLs and whole source_state/snapshot JSON. IDs preserve traversal to those
internal records under a future authorized audit path. NAME/PUBLICATION source
reference behavior is unchanged; this is not a redesign of legacy evidence.

See E3P3B2A_REVIEWER_CONTRACT.md for exact semantics and deferred release work.

## Isolation and decision safety

STAGED remains STAGED. No new route exposes source preview; existing current
observation/queue/dashboard reviewable queries remain COMPLETED-only. A staged
source root does not replace an existing completed NAME/PUBLICATION observation.
Even a manually misclassified completed source row is now refused by the live
serializer. Manually changing STAGED to COMPLETED is not a supported release.

AST checks prove `decide_review_candidate` and every other existing route function
outside the detail read are unchanged. CandidateReviewService (including snapshots,
ACCEPT/REJECT/promotion), review queries, IdentityEvidence, D-2 and accepted source
writers are byte-identical. All 16 existing API schema classes are AST-identical.
No actual reviewer action is run by this task or its new tests.

The new preview uses `session.no_autoflush` and only SELECTs. It has no commit,
flush, rollback, write, generation creation or status transition. SQL instrumentation
and a pending-invalid-caller-state test verify this on SQLite. Caller transaction
ownership remains intact.

STAGED roots already participate in some direct root counts, review-context
counts and ambiguity warnings/D-2 candidate counts. Those existing paths are
unchanged and do not expose source evidence or grant an ACCEPT. Queue/detail
selection still uses completed observations. Reconciling aggregate count semantics
is deferred to the authorized release design; no reason requirement is weakened.

## Validation actually executed

- Original-handler probes: both SOURCE_CLAIM and UNRECOGNIZED became PUBLICATION
  using exact pre-task handler source and isolated synthetic SQLite fixtures.
  The two probes confirm the former failure without changing working files.
- Final focused suite: **65 passed**, exit 0.
- Combined offline suite: **453 passed**, exit 0; 65 B2-A, 366 existing E3
  cases and 22 existing pure matching cases. No final failures/skips.
- Original delivery's first draft: 28 passed / 1 failed. A fixture altered frozen provenance but
  expected successful output; the accepted integrity guard correctly refused it.
  The privacy fixture was corrected to introduce private raw text before staging;
  a separate tamper-refusal case remains. This was not a production defect.
- The first sandboxed full run hit Windows WinError 5 on pytest temporary files.
  The approved fresh-directory rerun passed. No passing total is inferred from
  the failed run's progress dots.
- Launchers blocked socket connections and app.main/app.core.database/conftest
  initialization, disabled plugin autoload/cache/bytecode. Forbidden modules: [].
- Handler tests compile the actual read function body and inject dependencies;
  they do not start FastAPI, bypass a live auth endpoint or prove HTTP authorization.
- Ruff 0.17.3: zero new diagnostics. New reader/test/schema files are clean.
  The route has 5 pre-existing diagnostics, down from 6 after moving its long
  serialization line; full-file route lint remains non-clean. No suppression added.
  R1 service/test-only Ruff check is clean, exit 0; API/schema were not changed by R1.
- Scoped diff check, added-line whitespace and reverse patch preflight pass.
  Whole-worktree diff check still reports trailing Markdown whitespace in the
  three pre-existing dirty docs/research files; their bytes remain unchanged.

## Deferred work and limits

P3-B2-B must define and authorize source evidence exposure, review snapshots,
explicit promotion semantics compatible with IdentityEvidence, CURRENT/stale
checks at decision time and D-2 preservation. Frontend display/controls require
a later authorized integration; current clients still consume NAME/PUBLICATION
arrays only. The new source DTOs are intentionally not registered on a live route
or added to the current detail response. No production workflow is activated.

No migration source/execution or application/PostgreSQL connection. SQLite mirrors
do not verify PostgreSQL constraints, locking, transaction isolation or concurrent
ingest/review/generation consistency. Existing staging/G04/candidate migration and
PostgreSQL acceptance gates remain. Full historical reads/current recomputation
may be expensive; storage/performance and pagination are not benchmarked. The
unexposed helper requires a future authenticated ADMIN/REVIEWER boundary before
any network exposure. No authorization is inferred from possession of a candidate ID.

STOPPED after E3-P3-B2-A for independent review. P3-B2-B, P4 and activation not started.
