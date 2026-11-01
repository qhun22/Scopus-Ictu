# E3-P3-B2-D - Decision log

Date: 2026-10-30 (Asia/Bangkok). DESIGN-ONLY. Final package decision: **PARTIAL_DESIGN**. SOURCE_CLAIM production remains INACTIVE.

Statuses: PROPOSED means an architect recommendation for review; REQUIRED_INVARIANT means retained policy/safety constraint; OPEN_BLOCKER means a concrete owner decision/provisioning dependency. None authorizes implementation or changes an accepted frozen artifact.

| ID | Status | Decision / recommendation | Basis, alternative and owner action |
| --- | --- | --- | --- |
| D01 | PROPOSED; ratification required | Revision 2 chooses STANDARD whenever current independent qualification exists; exception only for authenticated insufficiency; no caller downgrade | User's proposed policy resolves audit F4. V1 implementation allows overlap. Do not backport silently or change V1 snapshots/tests. Ratify family/revision/digest and deactivation rules |
| D02 | OPEN_BLOCKER | Appoint an ICTU institutional issuing authority and independent verification authority, with governed trust anchors and complete scoped feeds | Website ownership, staging byte hashes and evidence enums are not authentication. Specific organizational systems/operators have not been identified in repo. ICTU/project owners must nominate and document them |
| D03 | OPEN_BLOCKER | HR/identity custodian governs opaque human IDs and account equivalence; independent security custodian governs scoped capabilities | No inference from email, name or lecturer linkage; no ADMIN grant bypass, self-issued or self-approved authority enrollment. Ratify dual-control provisioning, mergers, revocation and break-glass policy; absent policy denies |
| D04 | OPEN_BLOCKER | Bind freshness to signed complete checkpoints and local revocation ordering, with explicit policy parameters | Require MAX_RECEIPT_AGE by authority, MAX_FEED_LAG, MAX_CLOCK_SKEW, PROPOSAL_TTL, APPROVAL_TTL, MAX_TRANSACTION_DURATION. All remain UNSET -> deny. Choose values and define remote-revocation SLA before implementation acceptance |
| D05 | PROPOSED; schema approval required | Separate append-only authority, proposal, approval, finalization, provenance and assurance tables; insert-once lock row; no frozen enum expansion | CandidateReview is not a pending-approval store. JSON-only event relations rejected under A12. Review keys, constraints, triggers/functions, indexes and privileges before writing a migration |
| D06 | OPEN_BLOCKER | Narrow transaction-aware append writer plus hash-chain envelopes and externally authenticated checkpoints | DB hash alone does not stop a privileged rewrite. Approve key custody/checkpoint operator, canonical encoding and failure/quarantine procedure. Existing AuditService is a stub and actual services instantiate audit rows directly; central-writer reconciliation must be explicit |
| D07 | OPEN_BLOCKER | Exception assurance is separate INSTITUTIONAL_EXCEPTION; independent standard evidence mapping must be qualified and versioned | No fabricated IdentityEvidence; seven types unchanged. Approve sidecar linkage and M2.8/API/UI amendments before an exception identity is visible to approved-identity consumers |
| D08 | OPEN_BLOCKER | Compensation appends events and uses existing allowed identity transitions; no automatic negative reopen or direct evidence replacement | Ratify authorized compensators and dual-human exception compensation, which historical MappingReview is compensated, and candidate-history behavior. Pending-proposal cancellation is not a candidate REJECT/REOPEN |
| D09 | PROPOSED; all-writer coverage required | First release serializes sensitive operations on one ICTU guard; READ COMMITTED rereads follow lock acquisition | Avoid claiming a savepoint creates a coherent snapshot. More scalable per-scope/serializable designs deferred. All staging/rule/account/authority/identity writers must participate or be fenced. Current writers are not assumed to comply |
| D10 | PROPOSED; service contract review required | Caller owns outer transaction; isolated owned action savepoint; no parent autoflush/commit/rollback/close; outcome durable only after caller commit | Do not call legacy CandidateReviewService ACCEPT/REJECT unchanged: these commit. Full-transaction serialization/deadlock/connection failures cannot guarantee parent preservation; caller handles any complete retry. Ratify incompatible-caller detection and writer integration |
| D11 | REQUIRED_INVARIANT | Default-deny production composition and inactive SOURCE_CLAIM guard persist until separately approved release | No synthetic adapter, permissive environment fallback, config activation, migration or route in B2-D. Runtime matrices here are designs, never PASS |

## Branch transition examples to ratify with D01

| Original event | Current authoritative change | Proposed result |
| --- | --- | --- |
| Exception proposal, insufficient evidence | Qualifying independent evidence appears | Deny old approval/finalization; new human STANDARD proposal references supersession; no automatic assurance upgrade |
| Standard proposal | Assessment withdrawn, invalid, stale or authority unavailable | Deny; do not fallback to exception |
| Either branch | Hard conflict appears, source issuance revoked, source generation changes | Deny; preserve historical event; correction/resolution requires separately governed process |
| Either branch, revision 1 draft | Revision 2 is ratified | V1 remains historical simulation; no replay as production. Create a new revision-2 event after fresh checks |
| Existing final exception association | Qualifying evidence arrives later | No relabeling of finalization. New independently reviewed assurance transition/finalization under approved lifecycle, preserving exception history |

## Definition of completion for this gate

The requested designs, compatibility analysis, threat/test matrix and explicit blockers are delivered. Unresolved governance and freeze choices justify PARTIAL_DESIGN. No owner ratification is fabricated and no follow-on implementation is begun.
