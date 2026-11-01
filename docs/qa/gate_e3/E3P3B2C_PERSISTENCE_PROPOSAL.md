# E3-P3-B2-C — separate persistence/release proposal (NOT IMPLEMENTED)

Date: 2026-10-30. Design proposal only. No migration generated or executed.
SOURCE_CLAIM production workflow remains INACTIVE.

## Decisions needed before a schema change

The business branch HYBRID is locked. The outstanding decisions concern its
enforcement and representation, not whether institutional claims count as
independent evidence (they do not).

1. Define the formally authenticated ICTU source authority and how each issuance
   receipt binds an artifact digest, issuing organization, validity/revocation,
   verification method/version and verification metadata. Integrity-only harvest
   manifests and filenames cannot supply this authentication.
2. Select an authoritative human principal registry (including multiple accounts
   for one human, service identities and revocation) and explicit per-human
   exception proposal/approval grants. ADMIN alone must not confer a grant.
   Decide who can issue and revoke these grants and how current authorization
   participates in the final transaction. None of this exists in User today.
3. Approve independent verifier qualification rules and their versioned receipt
   authority. Preserve publisher author ORCID, registry DOI authorship claims,
   Scopus profile ORCID and duplicated source ORCIDs as different tiers. A DOI
   match/type literal alone is not identity qualification. Exact candidate pair,
   author-specific position/EID/DOI where applicable, conflicts, scope, freshness
   and authoritative issuer provenance must be verified before a QUALIFYING receipt.
4. Specify how independently verified versus institutional-exception assurance
   is durably linked and visible to downstream readers of APPROVED identity.
   Do not reuse the seven IdentityEvidence types for the institutional declaration.
   Do not publish an exception as independently verified through existing APIs.

## Minimal durable event design for separate approval

CandidateReview JSON alone cannot record a durable *pending* proposal and a later
independent authorization without implying a candidate decision. MappingReview's
existing action constraints likewise must not be repurposed.

Propose a separate append-only hybrid review event table (name and revision TBD),
with typed envelope and immutable canonical JSON/digest. It should record:

- Event ID, kind PROPOSE/AUTHORIZE/FINALIZE/REVOKE/SUPERSEDE, created_at from the
  trusted server/database, and policy ID/version and branch.
- Exact candidate/version, observation/run/rules/input hash, lecturer and Scopus
  author UUID and claimed ID, institutional source revision and snapshot digest.
- Reviewer and, where required, approver account and human principal IDs,
  auth_version and explicit grant/authority receipt references at each action.
- Reason, risk acknowledgment, original proposal/authorization digest references,
  current independent assessment receipts, institutional authenticity receipts,
  conflict evaluation, assurance basis and outcome.
- Compensation reference for revocation/supersession. Never UPDATE/DELETE an
  earlier proposal, authorization, review, evidence or audit event.

Require identity FKs, canonical digest checks, nonblank reasons, correct event
references, uniqueness for action idempotency and finalization of each proposal,
and different reviewer/approver account AND human IDs for exceptions. Cross-row
event/reference validity needs an independently reviewed SQL/service enforcement
design; a JSON field or a hash alone does not enforce separation of duties.
Assurance must reference the durable finalization event. An append-only assurance
transition record or separately approved equivalent is necessary if the current
identity contract cannot safely carry that reference. Do not add an institutional
IdentityEvidence enum to avoid this work.

Authoritative source/human/grant/verifier receipts may live in independently
governed stores, but finalization must have a defined, testable revocation/freshness
boundary. External read callbacks plus READ COMMITTED are not atomic authorization.
Choose a local versioned receipt/revocation projection or a separately reviewed
equivalent before implementing a production adapter. This gate creates none.

## Atomic finalization and replay proposal

In one caller-owned transaction: load the original persisted event (including
original timestamps); revalidate actor and both human principals/grants; bind
current policy/source/authority revisions; lock/version-check candidate and Scopus
ownership; validate CURRENT evidence, independent qualification or complete exception
authorization and all hard conflicts; append final decision snapshot, assurance,
candidate/identity transition and audit event atomically. Use a consistent snapshot
and serialization strategy explicitly tested on PostgreSQL, not SAVEPOINT alone.

Promote only independently qualifying evidence through an approved mapping.
Retain institutional declarations in the separate provenance contract. No exception
or proposal may silently reopen negative decisions or reinterpret existing canonical
identity status. Define negative-decision reopen and compensation semantics before
exposing these actions. Roll back the owned action savepoint on semantic/concurrency
failure while leaving prior caller work intact; no outer commit in a service helper.

Replay must load authoritative historical events and compare original context to
current eligibility. Never reconstruct original event time from a client receipt,
replace earlier facts with newer ones, trust client-recomputed hashes, or turn an
old approval into a new decision for another candidate. A unique event/action key
and constraints must prevent duplicate finalization across processes/retries.

## Required later evidence and migration controls

Separate owner approval of schema/freeze changes and authority provisioning comes
before migration implementation. A future append-only migration must not rewrite
published revisions. Validate upgrade/constraints/rollback behavior on an authorized
disposable PostgreSQL database, concurrent finalization/ownership/revocation races,
tampering/replay, actual authenticated HTTP role/grant isolation, and web E2E.
Require independent review before any activation. No recommended next gate is
automatically started by B2-C.
