# Gate E.1 — Prioritized implementation roadmap

Audit only, 2026-10-29. No fixes implemented. Priorities describe future work; they are not permission to import or alter identities. G IDs refer to `IDENTITY_EVIDENCE_GAP_ANALYSIS.md`; TC IDs refer to `TEST_CASE_DESIGN.md`.

## Preserve what already works

Keep multi-ID canonical cardinality, one approved owner per Scopus author, explicit human acceptance, reason policy, role checks, candidate row locks and stale observation/version checks. Keep EID-first canonical dedup, nullable DOI, full CSV author lists, raw provenance, distinct personal publication sets, multiple affiliations and source-specific affiliation resolution versions. Keep regenerated decisions and old evidence. Do not replace these with a new auto-matching system.

Evidence: `backend/app/models/identity.py:115-128`; `backend/app/services/candidate_review_service.py:547-790`; `backend/app/services/normalization/scopus_normalizer.py:517-606`; `backend/app/services/affiliation_import.py:248-319`; `backend/app/services/matching/candidate_persistence.py:494-604`. Existing tests need execution in an authorized isolated environment before a release claim.

## P0 — Confirmed conditional integrity defects

| Order | Work | Dependency / bounded scope | Acceptance |
|---|---|---|---|
| 0A | G01: detect ambiguous canonical repository URLs | Small change to existing known-publication mapping, no new canonical uniqueness or merge | TC-10; order-independent ambiguity; no affected writes on apply; unaffected unique URLs still work |
| 0B | G03/G04: author replay and transaction recovery | Compare existing author order; use local savepoints or full-batch retry; handle only expected unique races; leave EID canonical strategy intact | TC-05/18; error log records drift; previous batch work never silently lost; counters match committed state; unrelated failures visible |
| 0C | G02: qualify affiliation evidence sources | Separate aggregator entity from raw/publisher values before ORCID bridge. Preserve the valid publisher identifier-chain use case rather than requiring names for every bridge | TC-03/04/15/19; wrong entity name/ORCID cannot create VERIFIED slot affiliation; no canonical lecturer identity created by affiliation import |

These are separate reviewable changes, not a combined broad migration. Verify current data impact only in a later read-only DB assessment; do not mass repair associations or delete historical evidence based on this report.

## P1 — Critical workflow additions

1. **Source-claim intake (G05), then collision/presence lifecycle (G08).** Extend current source infrastructure with an all-profile/raw-claim boundary. Preserve 410 source records including no-publication profiles, duplicate ORCID claims, WEB source groups/primary/counts and unowned/zero-CSV IDs. Use snapshot/hash/URL provenance already established. Resolve candidates only against known canonical rows; unresolved external IDs remain claims. Gate implementation on P0 mapping protections. Tests TC-01/02/08/09/10/14/21.
2. **Complete evidence descriptors and persistent counter-evidence (G06/G07/G11).** Freeze author row/order/raw source/name, EID/DOI/ID and derivation; preserve source tiers and both directions; distinguish observed conflict from missing metadata. Introduce no numeric confidence scheme without a need. Decide whether DOI mismatch is a warning or blocking conflict; retain no-DOI title fallback. Align run rule metadata (G16). Tests TC-03/04/05/13/15/19.
3. **Compensating identity review and publication attribution (G09/G10).** Add explicit audited REVOKE/REOPEN only after transition, permission and count policies are agreed. Add per-lecturer/publication flag/exclusion for suspected mixed profiles; retain canonical publication and other lecturer links. Keep affiliation-override revocation separate. Tests TC-07/14/20.
4. **Count definitions (G12).** Preserve existing corpus total. Define a separate ICTU-eligible total and time/source scope; reuse EID and lecturer/EID dedup. Apply any paper-attribution decisions consistently to lists, exports and totals. Tests TC-11/12/21. This depends on policy and per-paper review, not just adding DISTINCT.

If scope is constrained, stage lossless claims first and keep them unapproved. Do not import them by manufacturing canonical author/publication evidence merely to fit existing candidate FKs.

## P2 — Required regression coverage and import hardening

- Execute existing isolated tests for multi-ID/ownership concurrency, retries, evidence snapshots, EID/provenance, affiliation conflicts and access controls. Current audit marks them NOT_EXECUTED.
- Add combined ingestion → generation → review → replay → withdrawal tests; standalone mocked API tests are insufficient. In particular `backend/tests/integration/test_lecturer_import_api.py:223-239` does one import despite its idempotency-oriented name.
- Add G01 duplicate URL, G03 same-pair changed-order and G04 late-batch IntegrityError cases. Existing different-author slot/retry tests do not cover those paths.
- Add original strings/embedded titles/initials/merged-token recall and homonym negatives (G13), and source row-summary checks (R-18). Do not broaden to fuzzy auto-approval.
- Make Craw apply's audit and data commit consistent or explicitly recoverable (G15). Freeze actual executed rule-set metadata (G16). Test file-change-between-preview/apply and concurrent replay; source/known-publication hash reuse has no global source-claim idempotency constraint yet.
- Verify applied migrations, privileges/immutability expectations, live import counts and potential URL collisions in a separately scoped runtime audit. A migration file or model docstring is not evidence of deployed state.

## P3 — UX and optional observation features

Add source-claim versus candidate versus approved badges, evidence origins and counter-evidence beside support, source-primary labels, count source/time/scope, and explicit claim withdrawal history. Correct affiliation “Identity verified” wording only together with fixing its proof provenance. Source Scopus-profile attempts (G14) should be timestamped observations, never MERGED/INVALID conclusions from unavailable pages. Academic publication notices (FINDING-011) may be stored separately if in scope; they do not decide identity.

No new person-clustering engine is necessary for first intake. Keep unresolved ICTU-affiliated author IDs distinct from “not ICTU”; preserve candidate grouping hints for later owner-approved work.

## Ingestion design decision and alternatives

| Option | Benefit | Integrity/trade-off | Decision |
|---|---|---|---|
| Broaden canonical lecturer upload to consume all raw claims | Reuses visible upload route | Current scalar canonical ORCID/uniqueness and direct master updates conflict with unverified duplicates; source-only ID has no proper representation | Keep master contract; optional explicit adapter later, not automatic interpretation of extra fields |
| Put every source claim directly into existing candidates | Reuses review queue | Candidate requires canonical lecturer/author FKs; cannot represent no owner, missing local author, source primary/count or withdrawn raw claim; NAME/PUBLICATION kinds imply stronger semantics | Reuse candidates only downstream of claim resolution |
| Extend Craw/source loader plus a separate claim boundary using existing snapshots and ADMIN preview/apply | Preserves lossless roster/claims and current human governance; smallest justified addition | Requires explicit claim/presence/collision schema or equivalent normalized projection; must retain source data securely | **Recommended**. An additional claim workflow within existing ingestion infrastructure, not a second unrelated ingestion framework |

Literal T1–T6 enums, review roles for compensation, hard conflict policy, completeness/withdrawal policy and institutional time basis require owner design approval. Those are future implementation decisions; this audit does not stop short of delivering a concrete recommendation.

## First implementation task handover

Start with **G01 fail-closed URL mapping**. Reproduce using two synthetic Lecturer rows with one repository URL, not live data. Change `KnownPublicationIngestionService._build_lecturer_index()` and its preview/apply consumers (`backend/app/services/lecturer_dataset/known_publication_ingestion.py:335-415`, `537-569`) to retain the candidate set and report ambiguity. Check CLI/web wrappers already treat nonzero ambiguous counts as blocking. Preserve existing unique mapping, snapshot reuse and KP dedup behavior. Add TC-10 plus one unaffected happy path and no-write assertion. No source schema migration, canonical merge, ownership decision or real import belongs in that change. In the same phase, schedule G02/G03/G04 as separate patches before any production enrichment/import.

## Explicit non-decisions and remaining verification

No assertion that 410 lecturer masters or 152 source IDs are present in DB. No assertion that G01/G04 has occurred in live data. No presumption that historical Scopus IDs were merged, that a suspected mixed profile is proven, that registry absence disproves identity, or that raw duplicated ORCID is invalid. Runtime tests, browser verification and applied migration checks remain outstanding. Gate E.1 documentation is ready for independent review; implementation is not authorized by completion of this audit.
