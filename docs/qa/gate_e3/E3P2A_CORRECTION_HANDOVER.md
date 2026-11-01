# E3-P2-A final design correction (P2A-S1, P2A-S2): handover for independent review

Date: 2026-10-29 · Status: **CORRECTION DELIVERED — STOPPED FOR INDEPENDENT REVIEW** (P2-B not started)

Scope:
- Changed: `adapters.py`, its test file and the staging schema proposal (revised in place, rev. 2).
- Not changed: the E3-P1 modules, `pyproject.toml`, G01–G04 and the Gate D evidence.
- Not created: no model, migration, database access, real import, commit or push.

## 1. P2A-S1: contract version in artifact persistence

**Reproduced.** Two artifacts that are identical except for `contract_version` (`1.0` / `1.1`):
- both parse;
- they have the same `content_hash` and the same `capture_hash`;
- their canonical bytes differ.

Rev. 1's `UNIQUE(content_id, capture_hash)` would have kept only one of them, and it stored no exact
version from which to rebuild either one.

**Fix (design and pure helpers):**
- `source_captures` is now a pure observation. `UNIQUE(content_id, capture_hash)` is kept: the same
  observation under two minor versions is one capture, so withdrawal never double-counts it.
- **New `source_artifacts` table**, one row per exact envelope:
  - it stores the exact `contract_version`, CHECK `^1\.[0-9]+$` (with PostgreSQL ARE semantics,
    `$` is end of string);
  - `UNIQUE(artifact_bytes_sha256)` is the artifact identity;
  - a composite FK pins its analysis to the same content **and** version.
- **Analyses** stay keyed by (content, contract version, rule versions). The version is never read
  from an analysis, because one content may have several.
- **Byte-exact reconstruction:** `adapters.reconstruct_artifact_bytes(source_system,
  contract_version, capture_json, content_json)`. P2-B checks the rebuilt bytes against
  `artifact_bytes_sha256` inside the ingest transaction.
- **Natural keys** for all three layers come from one place, `adapters.staging_keys(snapshot)`. It
  refuses dict-parsed snapshots (`ARTIFACT_BYTES_REQUIRED`) and non-canonical bytes
  (`ARTIFACT_NOT_CANONICAL`).
- **New ingest outcome `ARTIFACT_ADDED`:** known capture, new artifact. `ALREADY_INGESTED` is now
  decided by the artifact hash.

**Regressions:**

| Test | Proves |
|---|---|
| `test_contract_minor_versions_share_content_and_capture_but_not_artifact` | hashes and keys of the two versions |
| `test_proposed_unique_keys_keep_both_contract_versions` | ingesting 1.0, 1.1 and 1.0 again gives 1 content, 1 capture and 2 artifacts; rev. 1's key gives 1 |
| `test_artifact_bytes_are_rebuilt_only_with_the_stored_contract_version` | each artifact is rebuilt exactly, and the other version's number rebuilds the *other* artifact |
| `test_staging_keys_require_canonical_artifact_bytes` | refusals |

## 2. P2A-S2: fail-closed harvest completeness

**Reproduced on the accepted P2-A code:**
- `status="FAILED"`, zero cards = zero profiles, no drift, no failures → **COMPLETE**. This is the
  reviewer's case.
- A second gap, found by reading the harvester: a manifest saying `status="COMPLETE"` from a run
  whose semantic replay failed → **COMPLETE**.

**The real harvester's vocabulary** (Craw `ictu_harvester/full_harvest.py`, read-only):
- `manifest.status` is written only as `COMPLETE`, or as `COMPLETE_WITH_SOURCE_FAILURES` when any
  entity failed.
- A run whose offline semantic replay differs ends **BLOCKED**, but that word is only returned by
  the CLI. The manifest is written *before* the replay check. A blocked run therefore still leaves a
  manifest saying `COMPLETE`, and the success evidence is `semantic_replay.json`
  (`a_equals_b_equals_c`, per-run `file_hashes`).
- `source_entity_failures[].entity_type` is one of `lecturer`, `<kind>` or `<kind>_listing`, for
  the kinds publication, project, master_thesis, doctoral_thesis and learning_material.

The adapter's earlier `"profile"` failure type was an invented name and has been removed.

**Fix.** COMPLETE now requires **all** of the following:
- a success status;
- a status consistent with the failure list (`COMPLETE` ⇔ no failures,
  `COMPLETE_WITH_SOURCE_FAILURES` ⇔ some failures);
- a passed semantic replay whose `lecturers.json` hash equals the manifest's hash, in every replay
  pass (it replayed *this* file);
- matching card and lecturer counts;
- no drift;
- no `lecturer` failure.

Anything unknown, missing or inconsistent gives PARTIAL. `profiles_artifact` takes the optional
`semantic_replay` argument. `capture.completeness_basis` now records `manifest_status` and
`semantic_replay_verified`, and `capture.upstream` records the replay's combined hash.

**Probe of the accepted code against the corrected code, on the same inputs:**

| Case | Accepted P2-A | Corrected |
|---|---|---|
| FAILED, zero counts | COMPLETE | PARTIAL |
| COMPLETE manifest, replay mismatch (BLOCKED run) | COMPLETE | PARTIAL |

**Regressions:**
- `test_harvest_status_must_be_a_consistent_success`, 9 cases:
  - success with no failures → COMPLETE;
  - success with only a master-thesis, publication-listing or project failure → COMPLETE;
  - a lecturer failure → PARTIAL;
  - either status contradicting the failure list → PARTIAL;
  - `FAILED`, `BLOCKED` or a missing status → PARTIAL.
- `test_failed_status_with_matching_zero_counts_is_partial`.
- `test_success_status_without_verified_replay_is_partial`, 4 cases: no report, a mismatched replay,
  a replay of another file, and no file hashes.
- `test_failed_harvest_never_authorizes_withdrawal`: FAILED and BLOCKED captures give NOT_OBSERVED,
  never WITHDRAWN.
- `test_semantic_replay_must_be_an_object`.

**Real data** (read-only, aggregates): profiles stay **COMPLETE**, now on stronger evidence:
- status `COMPLETE_WITH_SOURCE_FAILURES`, consistent with exactly one failure, of type
  `master_thesis`;
- the replay was verified, and its `lecturers.json` hash equals the manifest's in passes A, B and C;
- 410 = 410 = 410, no drift.

The content hash is unchanged (`ca03511c…`); only the capture changes, because it now records the
evidence. The records (410) and claims (410 e-mail, 372 ORCID) are unchanged, and both guide
artifacts are byte-identical to the accepted run.

## 3. Verification

| Check | Result |
|---|---|
| E3-P1 + adapter suites (`--noconftest`) | **192 passed** (was 172), 0 skipped, 0 xfailed |
| Focused S1/S2 set | 26 passed |
| Ruff (source_claims + both test files) | exit 0 |
| Replay P1 → errata → closeout → P2-A → **correction** on an empty tree, `--whitespace=error` | all OK; 3/3 P2-A files reproduce the workspace; reverse check OK |
| E3-P1 files vs closeout hashes | 7/7 unchanged |
| `pyproject.toml` vs accepted P2-A | unchanged |
| Storage claims on the real artifacts (rebuild from content + capture + version; record hashes) | 3/3 true |
| Real run over 4 `PYTHONHASHSEED` values | one digest |
| G01–G04: 31 recorded files | 31/31 MATCH |
| `git status` | same 16 tracked modifications as after P2-A; no alembic, model, API or frontend change |

The tests ran with `--noconftest`, because the project conftest needs an allowlisted
PostgreSQL test DB. No database was used.

## 4. Correction history

1. **P2-A, accepted.** Adapters plus the rev. 1 schema proposal.
2. **Independent review** found S1 (contract-version collision in the rev. 1 keys) and S2 (completeness
   ignores the harvest status).
3. **S2:**
   - I read the harvester source and found the real vocabulary, and that a BLOCKED run still writes a
     COMPLETE manifest.
   - I added the status, consistency and replay conditions, and removed the invented `"profile"`
     failure type.
   - I reproduced both gaps on the accepted code and confirmed that both are closed.
4. **S1:**
   - I split artifact identity from capture identity (`source_artifacts`) and keyed analyses by
     version.
   - I added `staging_keys` and `reconstruct_artifact_bytes` as the single definition, with set-based
     regressions of the proposed UNIQUE constraints.
5. **Re-verification:**
   - 192 tests and Ruff;
   - the five-diff replay;
   - the real-data recheck: only the profile capture changed, and as intended.

## 5. Remaining boundaries (unchanged)

- **O-2 and O-7** remain owner decisions. The review recommends approving both: upstream raw files in
  a restricted store outside Git, with checksums and an agreed retention period; no birth date,
  gender or phone in staging.
- **P2A-S4.** P2-B must not gate ingest on whole-artifact JSON-Schema validity. Malformed rows stay
  as INVALID records, per the P1 contract. The proposal does not add such a gate.
- **G04.** The PostgreSQL isolation tests are still NOT_EXECUTED; no real-data database ingest is
  allowed before they pass.

## 6. Files

- `E3P2A_CORRECTION.diff`: narrow diff relative to the accepted P2-A (adapters.py +84/−7, test
  file +151/−6).
- `E3P2A_STAGING_SCHEMA_PROPOSAL.md`: revised in place (rev. 2). The old and new SHA-256 are in the
  validation JSON.
- `E3P2A_CORRECTION_TEST_RESULTS.txt` and `E3P2A_CORRECTION_VALIDATION.json`.
- The accepted P2-A deliverables (`E3P2A_HANDOVER.md`, `E3P2A_SOURCE_MAPPING.md`,
  `E3P2A_IMPLEMENTATION.diff`, `E3P2A_TEST_RESULTS.txt`, `E3P2A_VALIDATION.json`) were left
  unchanged, so their reviewed hashes still hold.

STOPPED after the correction. E3-P2-B not started.
