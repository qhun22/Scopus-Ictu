# E3-P3-B1 — evidence mapping and release boundary

Date: 2026-10-30 (Asia/Bangkok). Offline storage only; live release gated on P3-B2.

## Verified path

`source_rule_sets` newest sequence -> `source_capture_analyses` rank 1 / active ->
`source_claim_observations` -> retained SourceClaim/SourceRecord -> accepted P3-A
bridge -> candidate generation STAGED -> candidate observation -> SOURCE_CLAIM.

Current writer references in
`backend/app/services/matching/source_claim_candidate_persistence.py`:

| Function / lines | Responsibility |
| --- | --- |
| `_inputs`, 81–174 | Require one active analysis per capture; read the actual two accepted views; enrich claims with immutable source/raw references; load subject/catalog and existing decision context; call P3-A. |
| `_prepare`, 176–229 | Produce detached normalized descriptors, logical fingerprints, non-inflating weights and deterministic pair snapshots. |
| `persist_generation`, 231–280 | Flush caller state before a SAVEPOINT; atomically insert run/root/history; finish STAGED. |
| `_verify_run`, 282–312 | Check complete run membership, observation identity/snapshot, kind/rules/fingerprint/payload/source refs on replay. |
| `current_evidence`, 319–336 | Recompute active inputs, require verified matching STAGED history, collapse logical fingerprints. Offline only. |

`source_claim_matching/bridge.py` implementation is byte-identical to the accepted
pre-task version. Its URL/email resolution, multi-ID, negative decision echo,
scope/projection comparability and temporal tie rules are reused.

## Persistent representation

| Layer | Representation |
| --- | --- |
| CandidateGenerationRun | Dedicated rule set E3_SOURCE_CLAIM_CANDIDATES / E3-P3-B1/1; STAGED; source_state with active activation ID/versions, capture refs, complete source observations, bridge evidence/pairs/findings, deterministic input hash and P3-B2 release gate. |
| LecturerScopusCandidate | Existing lecturer/author pair root. New status PENDING; existing status/version/timestamps untouched. |
| Candidate observation | Pair assessment/reasons, normalized evidence descriptors, release gate; hash of the detached snapshot; one observation per pair/run. |
| Candidate evidence | evidence_kind SOURCE_CLAIM; bridge rule ID/version; normalized payload; full source_refs; logical evidence_fingerprint. |
| IdentityEvidence / reviews | No writes, migration, new vocabulary or promotion. |

Logical fingerprint:

`SHA256(canonical_json(["SOURCE_CLAIM", lecturer_uuid, author_uuid,
source_system, scope_key, projection_version, claim_key]))`

`claim_key` and subject UUIDs identify the declaration. Capture, artifact, analysis,
contract/active-rule/bridge-rule versions remain provenance, not additional logical
support. A rule change that actually changes the resolved subject, normalized claim
key or scope/projection can change logical identity; a relabeled/repeated observation
of the same declaration does not. No cross-source identity merge is inferred.

The normalized payload includes INSTITUTION_DECLARED, logical fingerprint, source
scope/projection/claim key, Scopus ID, URL/email subject-resolution method, active
identity/normalization versions, current state/weight and primary/listed flags.
Competing ownership and prior negative decisions are retained in the pair snapshot's
classification/reasons and generation findings. They are not verification scores.

Each evidence source_ref has capture, analysis, artifact, content, record and claim
IDs; contract/identity/normalization versions; artifact/content/capture/record hashes;
claim raw/normalized values/flags; record raw content/issues/validation/key method;
source URL and subject fields. Capture times/completeness are also retained in the
run's capture/bridge observation references. Exact staged IDs allow traversal to
the immutable capture envelope and all original source assertions.

Duplicate ORCIDs are never moved into a unique canonical field. Every original
source observation remains in source_state, with ORCID collision findings. ORCID
claims are diagnostic context, not invented Scopus pair proof. Ambiguous/unassigned
ID rows likewise remain findings and source history rather than owned pairs.

## CURRENT contract

1. Only the latest active SourceRuleSet selection may supply an analysis. Coverage
   must include exactly one selected analysis for every capture, including captures
   with no claims. Missing coverage fails closed; empty captures still affect absence.
2. The P3-A bridge compares captures within source_system/scope/projection. Withdrawal
   requires a strictly later comparable COMPLETE capture, with the bridge's full
   completeness/non-weak-key conditions. PARTIAL absence never withdraws. Equal-time
   contradictions never acquire chronology by UUID.
3. The descriptor overrides conflicting same-time flags to null and weight zero.
   INVALID rows and NOT_OBSERVED declarations have no current weight. A declaration
   marked unlisted cannot create current support.
4. `current_evidence()` verifies a stored STAGED run against today's full trusted
   recomputation. Stale input hashes do not select old history. Matching hashes are
   not sufficient: full state, observations and descriptors must also agree.
5. Multiple matching runs and repeated observations collapse to one logical
   fingerprint. Historical evidence-row counts, captured primary flags in the raw
   bridge result and sums of historical payload weights are not CURRENT facts.
6. No matching current run -> empty projection / zero current support until a new
   generation. Historical provenance remains available through stored runs/rows.

This deliberately favors missing current support over stale or ambiguous authority.
The binary weight means a usable institutional declaration exists; it is not a
probability, score, reviewer approval or verified identity tier.

## Reviewer P3-B2 work — deferred, not implemented

| Existing interface | Required later compatibility |
| --- | --- |
| `api/v1/endpoints/reviews.py:468-490` non-NAME serializer fallback | Explicit SOURCE_CLAIM schema/branch; tier, conflicts, raw provenance and CURRENT/history labeling; never publication-shaped output. |
| `candidate_review_queries.py:22-124` COMPLETED-only current observation | Deliberate release/selection policy for source evidence; stale active-rule/capture detection; no timestamp/UUID shortcut for source chronology. |
| `CandidateReviewService._build_evidence_snapshot` | Freeze normalized source state, current weight/conflicts, exact claim/capture/analysis/rules and evidence identity at decision time. |
| `CandidateReviewService._promote_candidate_evidence_to_identity` | Owner-approved SOURCE_CLAIM promotion semantics compatible with IdentityEvidence vocabulary; no disguise as existing verified evidence types. |
| `review_reason_policy.accept_reason_policy` | Preserve NAME_EVIDENCE_ONLY when no PUBLICATION; retain shared-author and multi-candidate reason requirements. |

All these production handlers remain unchanged. SOURCE_CLAIM is absent from the
promotion map, and STAGED observations do not replace an existing completed NAME
observation. Source-only roots do not enter the existing review queue/dashboard's
reviewable observation projection. Manual STAGED -> COMPLETED edits are prohibited
as a release procedure. No API, CLI integration or frontend path was added.

## Regression mapping

Tests are in `backend/tests/unit/test_source_claim_candidate_persistence.py`.

| Required category | Tests |
| --- | --- |
| Explicit kind, constraints, no unrelated promotion, D-2 | `test_source_only_candidate_is_pending_and_inactive_for_reviewers`, `test_model_checks_and_migration_source_agree_without_executing_migrations` |
| Source-only candidate despite no name match | `test_source_only_candidate_is_pending_and_inactive_for_reviewers` |
| Duplicate retry, captures, contracts, rules | `test_duplicate_run_replay_checks_everything_and_writes_nothing`, `test_repeated_captures_keep_provenance_without_weight_inflation`, `test_contract_variation_preserves_logical_fingerprint`, `test_rule_reanalysis_uses_active_analysis_and_not_stored_inactive_rows` |
| Withdrawal/history, PARTIAL, equal instants/flags | `test_withdrawal_zeroes_current_weight_but_retains_history`, `test_partial_and_equal_instant_absence_never_withdraw`, `test_same_time_flag_conflicts_are_not_scoring_facts`, `test_initial_ambiguous_flags_do_not_create_pending_pairs` |
| Multi-ID, ownership competition, duplicate ORCIDs | `test_multi_ids_and_competing_ownership_stay_separate`, `test_duplicate_orcid_claims_remain_visible_without_orcid_exact_evidence` |
| Negative/reviewed state preservation | `test_existing_candidate_reviewer_state_is_never_reopened`, `test_negative_identity_is_untouched_and_does_not_spawn_a_new_pending_pair` |
| Tampering, missing rows, aliasing | `test_replay_rejects_tampered_evidence_not_just_fingerprint`, `test_replay_rejects_tampered_observation`, `test_replay_rejects_tampered_run_provenance_and_missing_descriptors`, `test_json_payloads_are_detached_from_prepared_aliases` |
| Atomic failure, caller writes, retry, invalid pending state | `test_failure_is_atomic_retains_callers_writes_and_retry_works`, `test_prior_successful_generation_and_caller_write_survive_later_failure`, `test_pending_invalid_caller_state_fails_before_our_savepoint` |
| Fail-closed inputs / live compatibility | `test_missing_active_analysis_fails_closed`, `test_invalid_record_does_not_gain_weight`, `test_catalog_miss_stays_a_finding_without_inventing_an_author`, `test_existing_completed_name_observation_is_not_replaced_by_staged_source` |

39 parametrized P3-B1 cases passed on real isolated SQLite sessions. PostgreSQL,
deployment, concurrency/isolation and live reviewer acceptance remain unverified.
