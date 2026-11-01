# E3-P3-B2-D - Authority and persistence design report

Date: 2026-10-30 (Asia/Bangkok). Decision: **PARTIAL_DESIGN**.

DESIGN-ONLY. SOURCE_CLAIM production workflow remains **INACTIVE**. No application code, tests, model, migration, API route, configuration or frozen contract is changed. No commit, no push, no DB connection. This package proposes a future design; it does not authorize implementation, migration or activation.

## 1. Inputs and read-only baseline

Branch `main`; HEAD `4bb69f6efaac945399b1c191fc12879ad1c62885`. Before any B2-D output: 20 modified tracked files, 730 untracked file entries, 750 porcelain entries; 1,678 existing tracked/nonignored-untracked files. Complete status and file SHA-256 values are in `E3P3B2D_BASELINE.json`. Ignored/private/runtime data is excluded. No `.env` or private dataset was read.

The actual independent B2-C audit was found and read, rather than inferred from the previous conversation. Its original location was `C:/Users/QuangHuy/AppData/Local/Temp/E3P3B2C-independent-audit-20261030-xb2ck63r/INDEPENDENT_AUDIT_REPORT.md`; SHA-256 `d6d08d4fac549a350463260825f6347027c801fa306633a4dbbef9f58f4447d9`. Sandbox access initially failed; approved read access established that the file exists. An exact new input copy, `E3P3B2D_INPUT_AUDIT_REPORT.md`, preserves the dependency in this package. The original report is unchanged. Its character-encoding defects are retained, not silently corrected.

Read before design: actual `source_claim_hybrid.py`, B2-C HYBRID_CONTRACT and PERSISTENCE_PROPOSAL; independent audit F1-F4; B2-B code/decision contract; B2-A reviewer contract; identity/candidate/source-staging/governance/audit models; RBAC dependencies; review and staging transaction paths; existing migrations; M1.0, M2.7 and M2.8 freeze records; ADR-003/004. Read evidence and integrity checks are recorded in VALIDATION.

B2-C manifest: 6/6 hashes independently matched in this gate. Its prior 597 combined and 14 independent tests are **reported historical evidence**, not B2-D executions. B2-D ran no pytest, database, authenticated HTTP, browser E2E or frontend build. PostgreSQL behavior is only designed. The static revision graph has one head, `b88f02d44ff2`, above `a77e01c33ee1`; this was parsed from revision literals without importing Alembic's configuration/database environment. Older AGENTS/freeze head statements are historical, not the current graph.

## 2. Current implementation and gaps

| Boundary | Current evidence | Design response |
| --- | --- | --- |
| Independence and provenance | Hybrid `:74-123,189-220,269-306` validates typed authority outputs and staging bindings; it cannot authenticate their issuers | Governed signed authority receipts, complete assessment-set attestations and local revocation ledger |
| Same-human identity and grants | `User` has role/active/auth_version, no person registry or exception grants; hybrid `:259-265,409-416` trusts supplied linkage | Separate human registry and scoped capabilities; re-resolve equivalence at every action |
| Branch overlap | Hybrid `:250-256,359-369` can allow both branches | Proposed policy revision 2 with deterministic STANDARD precedence |
| History | Hybrid `:375,396-430` accepts trusted event-time arguments; no durable original event | Server/database event IDs and times, immutable envelopes, normalized references and authenticated checkpoints |
| Transactions | Hybrid `:389-418` owns a child savepoint, not a coherent global snapshot | One local guarded decision boundary, participating writers and atomic caller-owned finalization |
| Production guard | Hybrid `:432-434`; B2-B `:249-252` always refuse submission | Retain unchanged; all release gates remain separate |

## 3. Proposed deterministic branch policy

Proposed identity: family `SOURCE_CLAIM_HYBRID`, revision `2`, canonical policy document digest. This is a proposed successor to the current `(SOURCE_CLAIM_HYBRID_V1, 1)`, not a reinterpretation of V1. Exact public naming requires ratification (D01).

Compute the branch on the server from the complete, authenticated CURRENT assessment set for the exact candidate/lecturer/author/source context. First validate B2-B protections and authority availability/completeness. A verifier outage, expired checkpoint or malformed receipt is **UNKNOWN/BLOCKED**, never INSUFFICIENT. Signed absence/INSUFFICIENT from the responsible verifier is the only lack-of-evidence path. Do not permit callers to suppress a qualifying or conflicting receipt.

| Ordered condition | STANDARD eligible | EXCEPTION eligible | Outcome |
| --- | --- | --- | --- |
| Invalid context; unavailable/stale/incomplete authority; revoked selected source; invalid/withdrawn relevant assessment; unresolved hard conflict | No | No | Deny with stable reason; no fallback |
| At least one current qualifying independent assessment, with all common checks satisfied | Yes | No | Server selects STANDARD_INDEPENDENT |
| Current complete assessment set attests insufficient independent evidence; all selected active institutional artifacts formally verified | No | Yes for proposal | Server selects INSTITUTIONAL_EXCEPTION; grants, reason, risk acknowledgment and separate approval still required |
| Independent evidence insufficient but institutional provenance missing/unverified | No | No | Deny; source declaration alone cannot authorize acceptance |

An explicit weaker branch request when STANDARD is selected fails `HYBRID_BRANCH_MISMATCH`; it does not silently downgrade or coerce a proposal. The same applies to an explicit STANDARD request when only an exception proposal is eligible. These are proposed codes, not changes to current API contracts. Hard conflicts dominate a qualifying receipt. Invalid/withdrawn assessments are not reclassified as insufficiency. Revoked selected institutional issuance continues to block both branches; otherwise STANDARD may retain explicitly unverified institutional context, as V1 allows.

Reason/D-2, exact source generation, completeness, identity ownership, negative history and authenticated human requirements remain prerequisites. STANDARD still needs a human decision; qualification never auto-approves. An exception never becomes independently verified after approval. For STANDARD the reviewer needs the proposed STANDARD_REVIEW capability as well as existing ADMIN/REVIEWER RBAC. Exception requires EXCEPTION_PROPOSE and EXCEPTION_APPROVE capabilities with different accounts AND current canonical humans. ADMIN grants none of these implicitly.

On approval/finalization, re-evaluate under the proposal's immutable policy revision and current compatible policy activation. If a new independent receipt would change exception to STANDARD, or source/authority/policy context changes, refuse the old event. Require an explicit new human proposal linked by supersession. Never mutate its branch, upgrade assurance automatically, migrate a V1 draft, or replace the historical event. Exact same input revisions yield identical eligibility; event IDs/times are separate server-issued history fields.

## 4. Frozen-contract compatibility and explicit incompatibilities

| Contract | Compatible design requirement | Incompatibility / approval needed |
| --- | --- | --- |
| B2-B accepted offline boundary | Preserve all source/current/version/conflict/history/D-2 checks and inactive submit | It has no source decision mutation contract; future finalization is a separately reviewed service, not reuse of `submit` |
| B2-C V1 offline policy | Evidence/decision separation, denial precedence, distinct humans and nonfinal drafts retained | Exclusive branch precedence changes V1's actual overlap; new revision plus new future tests required. V1 code/tests/artifacts remain unchanged |
| M1.0 A08 / ADR-003 | All new authority/provenance/proposal/approval/history/audit rows append-only; compensation by new events | New tables/DB writer privileges/functions require schema approval; no schema edits in this gate |
| M1.0 A12 | Important relationships use typed columns/FKs, not only JSON references | Snapshot JSON alone cannot enforce same-pair approvals or event lineage |
| IdentityEvidence seven-type vocabulary / ADR-004 | No SOURCE_CLAIM enum or fabricated NAME/DOI/ORCID/APPROVED_ID promotion | Future standard promotion needs independently justified mapping. Exception declaration stays separate |
| M1.0 identity/review states | Existing APPROVED uniqueness, optimistic version, negative reopen and MappingReview transitions preserved | New exception assurance cannot be represented honestly by existing evidence alone; sidecar assurance plus consumer contract amendment required |
| M2.7 review service/API | Existing behavior untouched | `CandidateReviewService` commits at `:790,947`; calling it from the proposed borrowed transaction would commit caller work. Cannot reuse it unchanged as a finalization primitive |
| M2.8 approved identity consumption | No change to present read APIs | Current safe fields omit assurance. Exception identity release is blocked until separately approved APIs/UI display its basis and all consumers are assessed; a JSON snapshot or sidecar alone does not fix old readers |
| Audit single writer | Future hybrid audit append uses one reviewed transaction-aware audit writer | `AuditService.record` is a stub; candidate service directly constructs AuditEvent (`:527`) and staging does too. Do not claim an already-operational central audit authority. Reconciliation is an implementation prerequisite |

No frozen document is amended by this package. A design recommendation is not explicit permission to change a frozen schema or service contract.

## 5. Selected architectural proposal

Use governed external sources to issue authenticated receipts, imported into an append-only **local authority ledger** through a restricted ingestion boundary. Use that ledger, complete signed checkpoints and a single institution guard for synchronous decision validation. No network authority callback runs inside the finalization transaction. No synthetic fixture or cache substitutes for a missing production authority.

Authority source/issuer selection is **BLOCKED** until named ICTU custodians and independent verifier operators attest responsibility. No existing source filename, domain, Craw manifest, repository profile, account role or ORCID/DOI string is treated as that authority. Receipt and event authenticity requires approved key custody, trust anchors, issuance/revocation procedures and bounded freshness. Exact freshness parameters remain unset and therefore fail closed.

All domain history is append-only. A permanent, insert-once guard row provides locking without a mutable event cursor. Normalized event/proposal/approval/finalization/provenance/assurance tables reference existing candidate, source and identity tables with RESTRICT FKs. Current state is derived from verified event chains. Only the existing allowed aggregate roots would change during a separately approved finalization. See AUTHORITY_CONTRACTS and PERSISTENCE_DESIGN for exact relationships and enforcement allocation.

For the first proposed release choose a coarse institution-wide guarded READ COMMITTED protocol: all relevant source, rule, policy, authority, permission, human-link and identity-decision writers must acquire the same guard before domain reads/writes. After acquisition, reread authoritative rows and retain the lock to outer commit. Row locks and the existing approved-owner unique index remain required. This is a deliberate protocol, not a claim that SAVEPOINT or READ COMMITTED alone provides snapshot consistency. Legacy/direct writers must be adapted or technically fenced before release. Until that coverage is proven, finalization is BLOCKED.

The security ordering boundary is the guarded local decision event, not instantaneous knowledge of a remote revocation. Maximum checkpoint lag, validity at decision time, bounded transaction duration and subsequent compensating revocations require owner ratification. No architecture can assert a remote change it has not received. This limitation is explicit rather than hidden behind a CURRENT flag.

## 6. Deliverables and audit closure mapping

| B2-C finding | B2-D design location | Remaining blocker |
| --- | --- | --- |
| F1 - missing real authorities | AUTHORITY_CONTRACTS sections 1-7 | Source owners, issuer keys, complete feeds, human registry and grants not provisioned |
| F2 - unauthenticated historical time | PERSISTENCE_DESIGN sections 2-5,8 | Durable authenticated writer/checkpoint infrastructure not implemented |
| F3 - transaction/revocation and callback safety | PERSISTENCE_DESIGN sections 6-7; SECURITY_TEST_MATRIX | All-writer guard coverage, DB permissions and PostgreSQL race tests not executed |
| F4 - overlapping eligibility | This report section 3; DECISION_LOG D01 | Ratify proposed revision-2 precedence; V1 intentionally unchanged |

Required five design documents plus manifest are supplied. Supporting BASELINE, INPUT_AUDIT_REPORT, HANDOVER, VALIDATION, TEST_RESULTS and IMPLEMENTATION.diff provide provenance and change evidence. The diff contains new documentation only; no executable migration or application patch.

## 7. Remaining decisions, blockers and stopping point

Decision **PARTIAL_DESIGN** means the technical design is available for review, while named authority sources, policy ratification and frozen-contract approvals remain unresolved. It is not a runtime verdict. A missing input audit would have blocked this gate; that dependency was actually recovered and read.

1. Ratify revision-2 precedence, proposal invalidation on branch change and exact version identity (D01).
2. Name institutional/verifier/person/grant/audit custodians, trust anchors, key recovery and grant governance; approve freshness/lag and coverage semantics (D02-D04).
3. Approve the append-only schema proposal, narrow trusted DB append boundary and assured history checkpoint design (D05-D06).
4. Approve explicit standard promotion and exception sidecar/consumer freeze changes; define compensation and negative-lifecycle rules (D07-D08).
5. Approve the coarse guard protocol and adaptations of every relevant legacy writer, borrowed-transaction API and revocation ordering guarantee (D09-D10).
6. Separately authorize implementation and disposable PostgreSQL, authenticated HTTP/JWT and web E2E acceptance gates. None is executed or authorized here (D11).

SOURCE_CLAIM production remains **INACTIVE**. Stop after the design artifacts. Do not implement B2-D.
