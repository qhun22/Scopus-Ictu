# E3-P3-B2-A — reviewer evidence/read contract

Date: 2026-10-30 (Asia/Bangkok). Offline compatibility contract, not a release.

## Production boundary

`reviews.review_candidate_detail` still resolves only the existing completed
observation through `current_reviewable_observation`. It now calls
`serialize_review_evidence(evidence_rows, publications)` explicitly:

| Persisted kind | Result |
| --- | --- |
| NAME | Existing ReviewNameEvidenceResponse, unchanged fields/reference behavior. |
| PUBLICATION | Existing ReviewPublicationEvidenceResponse, unchanged canonical lookup/payload fallback. |
| SOURCE_CLAIM | APIError 409 SOURCE_CLAIM_REVIEW_INACTIVE; no publication-shaped result. |
| Any other value | APIError 409 CANDIDATE_EVIDENCE_KIND_UNSUPPORTED; no default branch to publication. |

Errors use static messages and do not embed raw payloads. Existing role checks,
queue categories, NAME/PUBLICATION counts, detail response schema, request schemas
and decision handlers remain unchanged. A mixed observation with an unsupported
kind fails as a whole; partial evidence lists are not returned as a successful read.

No SOURCE_CLAIM route, queue addition or frontend rendering is introduced.
Frontend `types/review.ts`, `api/reviews.ts` and ApprovalQueue consumers remain
unchanged. They receive the original arrays or a fail-closed error. New source DTOs
are separate from the current HTTP detail schema and are not advertised as a live
OpenAPI endpoint. This avoids a contract that the current frontend would ignore
or misrepresent while decision integration is still blocked.

## Future offline read entrypoint

`source_claim_read_preview(session, candidate_id)` is implemented in
`backend/app/services/candidate_evidence_read.py`. It takes a local SQLAlchemy
session and returns `ReviewSourceClaimProjectionResponse`. It performs no writes,
commits/rollbacks/autoflush, route registration or authorization. It must not be
exposed to a client without a separately authorized ADMIN/REVIEWER boundary.

Top-level fields:

| Field | Meaning |
| --- | --- |
| candidate_id / candidate_status | Existing root identity and current status, never modified. |
| reviewer_active | Literal false. |
| decision_enabled | Literal false, regardless of usable declaration weight. |
| release_gate | E3-P3-B2_REQUIRED, matching the accepted storage gate. |
| items | One item per logical SOURCE_CLAIM fingerprint for this candidate. |

Each item has SOURCE_CLAIM and INSTITUTION_DECLARED literals, fingerprint, source
system, hashed scope key and catalog Scopus ID. `subject_resolution` is available
only for an active projection; recorded methods are listed separately. No actual
subject e-mail, claim key or source row name is copied into the response.

## Authority, history and ambiguity

| selection_status / current_state | Weight and flags |
| --- | --- |
| ACTIVE_PROJECTION / CURRENT | Weight 1; listed=true; primary flag from the accepted normalized descriptor. This means usable institutional declaration, not identity verification. |
| ACTIVE_PROJECTION / WITHDRAWN | Weight 0; primary/listed current flags null; history retained. |
| ACTIVE_PROJECTION / NOT_OBSERVED | Weight 0; absence in PARTIAL captures proves no withdrawal. |
| ACTIVE_PROJECTION / AMBIGUOUS | Weight 0; temporal_ambiguity=true; primary/listed current flags null. |
| ACTIVE_PROJECTION / INVALID | Weight 0; not authoritative. |
| HISTORICAL_ONLY / STALE | Weight 0; current subject method/flags null; all traces historical. Old payload state never supplies fallback CURRENT authority. |

The schema validates these state/weight/flag relationships and requires non-empty
history/provenance. Recorded states and recorded_conflict_codes are historical
context, not current conclusions. The conflict code whitelist includes competing
owners, approved-elsewhere/negative-decision context, unowned-list conflicts and
withdrawal. No free-form finding details, raw JSON or arbitrary caller flags are
forwarded. Current temporal ambiguity and historical AMBIGUOUS states are separate.

CURRENT authority comes solely from the accepted B1 writer's public
`current_evidence()`, which reevaluates active staging analyses and trusted bridge
inputs, verifies matching STAGED runs and deduplicates logical fingerprints.
The B2-A reader does not change that algorithm or select an old run by timestamp,
creation order or UUID. New captures, reanalysis/activation and relevant review
changes stale old generations. If current integrity/coverage cannot be proved,
the reader returns SOURCE_CLAIM_PROJECTION_UNAVAILABLE, not manufactured CURRENT.

Before showing history, the reader checks pair membership, snapshot/hash,
descriptor membership, kind/tier, logical fingerprint and matching source refs in
the stored generation. B2A-R1 additionally verifies the full historical source_state
digest BEFORE using any capture metadata: input_hash must match
`sha256_json({k: v for k, v in state.items() if k != "input_hash"})`, using the
unchanged B1 utility. State/capture containers and consumed capture fields must have
the expected types; capture IDs cannot repeat, timestamps require UTC offsets and
completeness must be COMPLETE or PARTIAL. A missing, malformed or mismatched digest,
or a malformed envelope, raises SOURCE_CLAIM_EVIDENCE_INVALID. No stored digest or
historical value is overwritten and no invalid provenance is silently dropped.
History validation precedes CURRENT projection, so malformed historical state does
not enter the accepted B1 reader first. History is not proof of current authority. Corruption is
refused with SOURCE_CLAIM_EVIDENCE_INVALID (or the projection-unavailable code
when the separate CURRENT verifier cannot establish a current projection).

## Trace allowlist and privacy

`history` retains evidence_id, observation_id, generation_run_id, rule_id,
rule_version and recorded_state. Repeated run rows remain traceable here and do
not create more current logical items.
History/trace array order is deterministic display order, not chronology by UUID;
capture timestamps carry observation time and the accepted bridge decides presence.

Each `source_refs` entry contains ONLY:

- capture_id, analysis_id, artifact_id, content_id, claim_id, record_id;
- contract_version, identity_rules_version, normalization_version;
- offset-aware captured_at, completeness;
- ACTIVE_PROJECTION/HISTORICAL_ONLY trace selection label.

Trace selection means selected under the currently active projection. It does
not mean the declaration is currently listed or has weight 1: a WITHDRAWN item
can still refer to its earlier observation through the active analysis. Old
analysis/contract traces remain explicitly historical after reanalysis.

The reader builds new typed values instead of forwarding payload/source_refs/
source_state/snapshot dictionaries. Excluded fields include record_raw, issues,
record/claim/subject keys, raw/normalized source-value blobs, record e-mail,
ORCID context, arbitrary flags, source URLs and unrelated private profile fields.
The UUIDs preserve internal traceability without copying these values into the
future reviewer contract. Original data remains intact in staging/history.

## Existing read paths and decision protection

| Path | B2-A treatment |
| --- | --- |
| Queue/detail completed-observation selection | Unchanged; STAGED excluded. |
| Dashboard pending-review count | Unchanged shared reviewable-candidate subquery. |
| Review context aggregate counts | Still counts roots by status and completed runs separately; a root count is not a reviewable evidence count. |
| Ambiguity warnings/D-2 candidate counts | Existing root-count semantics retained; staged roots may add warnings/reasons, never waive them. |
| ACCEPT/REJECT/REOPEN/REVOKE and promotion | No business-logic changes or execution. SOURCE_CLAIM remains absent from the IdentityEvidence promotion map. |

Tested source-only roots stay out of the current queue, and source history does
not supersede an existing completed NAME observation. An accidentally/manual
COMPLETED source row now fails at serialization. This extra guard is not permission
to promote STAGED generations or to review source claims through existing endpoints.

## P3-B2-B authorization/promotion work — deferred

1. Authorize explicit reviewer access/exposure and define the safe release route
   and lifecycle. Reconcile direct root-count/context semantics; preserve queue isolation.
2. Freeze a decision-time source snapshot with source tier, logical evidence identity,
   exact claim/capture/analysis/rules, CURRENT state and conflict/ambiguity context.
3. Design an explicit IdentityEvidence representation/promotion policy approved by
   the owner; do not disguise institutional declarations as publisher ORCID, DOI,
   NAME, PUBLICATION or APPROVED_ID evidence. No such promotion is added here.
4. Recheck active analyses/captures and observation/version under the actual decision
   transaction; preserve prior negative-state reopen protection and approved identities.
5. Preserve D-2 NAME_EVIDENCE_ONLY when no PUBLICATION, plus shared-author and multiple-
   candidate reason requirements. A source declaration weight never bypasses these.
6. Complete authorized PostgreSQL migration/savepoint/concurrency/isolation checks,
   frontend contract/display integration and independent release review before activation.

No schema migration or frontend changes were needed for B2-A. PostgreSQL and HTTP
authorization/E2E remain NOT_EXECUTED; no production exposure is claimed.
