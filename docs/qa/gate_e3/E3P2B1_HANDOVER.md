# E3-P2-B1 — Staging schema, models and migration: handover for independent review

Date: 2026-10-29 · Status: **B1 DELIVERED — STOPPED FOR INDEPENDENT REVIEW** (B2 not started)

Migration execution: **NOT_EXECUTED.** No `TEST_DATABASE_URL` or allowlisted disposable PostgreSQL
database is configured. Nothing connected to, or changed, any database. The migration was
rendered offline only (PostgreSQL dialect, `as_sql`).

## 1. Files

| File | Change |
|---|---|
| `backend/app/models/source_staging.py` | **new**: 7 models, vocabularies, the 2 view SQL bodies |
| `backend/alembic/versions/a77e01c33ee1_e3_p2b1_source_claim_staging.py` | **new** migration, `down_revision = a1b2c3d4e5f6`; the single new head |
| `backend/app/services/source_claims/provenance.py` | **new**: pure input-file binding for B2 (§4) |
| `backend/app/models/__init__.py` | +1 line, registers `source_staging` |
| `backend/tests/unit/test_source_staging_schema.py` | **new**, 23 tests |
| `backend/tests/unit/test_source_claims_provenance.py` | **new**, 15 tests |

Unchanged:
- the accepted E3-P1 / P2-A code, tests, schema and `pyproject.toml` (10/10 hashes);
- G01–G04 (31/31);
- the Gate D evidence and research documents.

There is no API, no service, no data import, and no ACCEPT, REJECT, REVOKE or MERGE.

## 2. The two required resolutions

### A. Rule-version reanalysis

An existing artifact never blocks an analysis.

**Schema change from rev. 2:** `source_artifacts` **no longer has `analysis_id`**. An analysis is
found by its own key, `UNIQUE(content_id, contract_version, identity_rules_version,
normalization_version)`. A new rule version therefore only *adds* `source_analyses`,
`source_records` and `source_claims` rows. It updates nothing, and old analyses stay.

**Lifecycle for B2:** each layer is checked on its own key, in order. There is no early return.

| Layer | Key | When it already exists |
|---|---|---|
| content | `(source_system, content_hash)` | reuse |
| capture | `(content_id, capture_hash)` | reuse |
| artifact | `artifact_bytes_sha256` | reuse |
| analysis | `(content_id, contract_version, rule versions)` | reuse; otherwise insert the analysis and its records and claims |

**Outcome**, reported for the first layer that was new:

| First new layer | Outcome |
|---|---|
| content | `CREATED` |
| capture | `REUSED` |
| artifact | `ARTIFACT_ADDED` |
| analysis | `REANALYSED` |
| none | `ALREADY_INGESTED`, now only when *all four* layers already exist |

**Reanalysis without upstream input:** rebuild each stored artifact with
`adapters.reconstruct_artifact_bytes(...)`, re-parse it under the current code, then ensure the
analysis. This is idempotent.

**Rule activation:** the new append-only `source_rule_sets` log (`sequence_no` IDENTITY, unique).
The row with the highest `sequence_no` is active. Re-activating old rules adds a new row; it never
updates one.

**Tests (executable, SQLite stand-ins):**
- `test_rule_version_change_reanalyses_an_existing_artifact`:
  - re-ingesting the same bytes under rules v2 gives `REANALYSED` with layers
    `{content: F, capture: F, artifact: F, analysis: T}`;
  - the artifact rows are byte-identical before and after;
  - the v1 analysis remains (rank 2, inactive);
  - the claims of both versions are kept.
- `test_reanalysis_from_stored_rows_needs_no_upstream_input`: 2 new analyses, then 0 on a second run.
- `test_switching_back_to_an_older_rule_set_reselects_its_analysis`.
- `test_re_ingesting_the_same_artifact_writes_nothing`: `ALREADY_INGESTED`, row counts unchanged.

### B. Claim-observation view

The view never double-counts. Its selection SQL is fixed and executable (identical text in the
model and the migration; a test asserts equality). There are two views:

**`source_capture_analyses`** lists **all** (capture, analysis) pairs, so history stays queryable.
Each pair carries `is_active_rule_set` and a `selection_rank`.
- An analysis is compatible with a capture only through one of that capture's artifacts:
  `an.content_id = art.content_id AND an.contract_version = art.contract_version`.
- `selection_rank = ROW_NUMBER() OVER (PARTITION BY capture_id ORDER BY …)`, ordered by:
  1. analyses under the active rule set first;
  2. then the highest contract minor, `CAST(SUBSTR(contract_version, 3) AS INTEGER) DESC`
     (the CHECK pins the major to `1`);
  3. then the newest analysis;
  4. then `analysis_id`, as a total-order tie-break.

**`source_claim_observations`** = `source_capture_analyses` with `selection_rank = 1 AND
is_active_rule_set = 1`, joined to `source_claims` on `analysis_id`.

**Why the result is unique per (capture, claim):**
1. Rank 1 selects exactly one analysis per capture.
2. A claim belongs to exactly one analysis.
3. `UNIQUE(analysis, contract_version, rules)` and the new `UNIQUE(capture_id, contract_version)`
   on artifacts give each (capture, analysis) pair exactly one artifact path. That uniqueness is
   implied by the bytes already, and is now a database guarantee.

**Rule versions:**
- Under an activated rule set that has no analysis yet, a capture has **no** observations. Rules are
  never mixed, and B2's reanalysis fills the gap.
- Re-activating an older rule set re-selects its existing analyses with no write.

**Tests:**
- `test_two_minor_versions_share_one_capture_and_are_observed_once`: 1 content, 1 capture,
  2 artifacts, 2 analyses; observations equal the claims of one analysis, from version 1.1.
- `test_a_naive_capture_artifact_analysis_join_would_double_count`: the naive join yields exactly 2×.
- `test_recaptured_content_is_observed_per_capture`.
- `_assert_no_duplicate_observations` runs in every scenario: (capture, claim) is unique, with one
  analysis per capture.

**Mutation probes** (see the test log): removing the rank filter fails 4 tests, and removing the
active-rule filter fails 2 tests. Behavioural tests catch both, not only the text-equality test.

## 3. DDL decisions

| Table | Keys and constraints (names follow the frozen naming convention) |
|---|---|
| `source_rule_sets` | PK `id`; `sequence_no` BIGINT IDENTITY, UNIQUE; FK `activated_by → users` RESTRICT; non-blank versions |
| `source_contents` | UNIQUE(`source_system`, `content_hash`), UNIQUE(`id`, `source_system`); CHECK `content_hash = encode(sha256(convert_to(content_json,'UTF8')),'hex')`; hex, system and `contract_major = 1` CHECKs |
| `source_captures` | composite FK (`content_id`, `source_system`) → contents; UNIQUE(`content_id`, `capture_hash`), UNIQUE(`id`, `content_id`); capture JSON hash CHECK; completeness CHECK; non-blank adapter and projection versions |
| `source_artifacts` | composite FK (`capture_id`, `content_id`) → captures; **UNIQUE(`artifact_bytes_sha256`)**; **UNIQUE(`capture_id`, `contract_version`)**; CHECK `contract_version ~ '^1\.[0-9]+$'` (PostgreSQL ARE `$` = end of string); FK `ingested_by → users` |
| `source_analyses` | FK → contents; UNIQUE(content, version, identity rules, normalization rules); JSONB array/object CHECKs; counts ≥ 0 |
| `source_records` | FK → analyses; UNIQUE(`analysis_id`, `record_kind`, `source_position`), UNIQUE(`id`, `analysis_id`); CHECK key method ⇔ strength (from P1); **no unique on `record_key`** |
| `source_claims` | composite FK (`record_id`, `analysis_id`) → records (a claim cannot cross analyses); UNIQUE(`record_id`, `claim_key`) only; CHECK subject NULL ⇔ ambiguous/unassigned; CHECK `claim_key` starts with `claim_type|`; `value_valid` generated (STORED, NOT NULL) |

**Invariants:**
- **No global UNIQUE** on ORCID, names, e-mail, `record_key`, `claim_key` or values. The test
  `test_unique_constraints_are_exactly_the_designed_ones` pins the full inventory, so any new unique
  constraint fails it.
- **Isolation:** the only external FK is `users` (the actor). No existing table references a staging
  table, and no staging column names a lecturer, Scopus author, candidate, identity, status or
  decision (tested).
- **Append-only:** no `updated_at`, the repository's existing convention (M1.0-A08). There are no
  triggers, consistent with every existing migration.
- **Not reused:** `lecturer_source_snapshots` is lecturer-attached, and `scopus_imports` is a mutable
  status machine. `audit_events` is reserved for B2's ingest audit.

## 4. Input-file trust boundary (for the B2 file reader)

`adapters.profiles_artifact` trusts the objects it receives. The reviewer's probe still holds, and
the test `test_adapter_alone_does_not_bind_caller_input_but_the_reader_does` pins it: an unrelated
`lecturers_sha256` passed straight to the adapter still yields COMPLETE. A self-consistent manifest
and replay prove nothing about arbitrary caller input.

`provenance.bind_harvest_files(...)` is pure: the caller passes the **exact file bytes**. It:
1. decodes the bytes itself, rejecting duplicate JSON keys, non-UTF-8 input and non-bytes input;
2. requires `sha256(lecturers bytes) == declared SHA-256`;
3. requires the harvester's semantic hash of the decoded list to equal
   `manifest.semantic_file_hashes["lecturers.json"]` (the algorithm is reproduced from Craw
   `full_harvest.semantic_hash`);
4. requires every replay pass to have passed, and to record both that hash **and** the manifest's own
   semantic hash;
5. optionally applies the same check to the crawl report.

**B2 must feed the adapter only the objects returned by this function.**
- **Real files** (read-only, booleans only): they bind; 410 profiles; the semantic hash equals the
  manifest's; the adapter gives COMPLETE on the bound objects; a wrong declared SHA is rejected
  (`BYTES_SHA256_MISMATCH`).
- **Residual:** the harvester's semantic hash ignores `retrieved_at` and similar timestamps, so those
  are bound only by the exact-bytes SHA. This is tested. There is no cryptographic signature, so a
  party who rewrites all four files consistently is not detected. Custody of the raw files (O-2)
  remains the anchor.

## 5. Verification

| Check | Result |
|---|---|
| E3 pure suites + B1 schema + provenance (`--noconftest`) | **230 passed** (192 + 23 + 15), 0 skipped, 0 xfailed |
| B1 focused (schema + provenance) | 38 passed |
| Ruff on all B1 files and source_claims | exit 0. `app/models/__init__.py` has an I001 that already exists at HEAD (B1 only adds one import line) |
| Offline migration render | upgrade: 7 CREATE TABLE, 11 CREATE INDEX, 2 CREATE VIEW; downgrade: 2 DROP VIEW, 11 DROP INDEX, 7 DROP TABLE in reverse dependency order |
| Migration ⇔ models | item-by-item CREATE TABLE equality (this caught and fixed one drift: `value_valid NOT NULL`); index set equality; view text equality |
| Alembic graph (static) | 14 revisions, single head `a77e01c33ee1` |
| Six-diff replay (P1 → errata → closeout → P2-A → correction → B1) on an empty tree, `--whitespace=error` | all OK; 6/6 B1 files reproduce the workspace; reverse check OK |
| Accepted E3 files | 10/10 unchanged |
| G01–G04: 31 recorded files | 31/31 MATCH |
| `git status` | the P2-A set plus `backend/app/models/__init__.py`; the only alembic change is the new revision file |

## 6. Remaining risks (for review and the PostgreSQL gate)

1. **No PostgreSQL execution.** The following have only been rendered and string-checked:
   - the CHECKs that use `~`, `sha256()`, `convert_to`, `left()` and `jsonb_typeof`;
   - `GENERATED … STORED`, `GENERATED ALWAYS AS IDENTITY`, the composite FKs and both views on
     PostgreSQL 16.

   The SQLite stand-ins execute the view logic, the UNIQUE constraints and the staging FKs, but not
   the CHECKs or JSONB.
2. **Integration fixtures use `Base.metadata.create_all`.** On their next authorized run they will
   create the 7 staging tables but **not the views**. B2 tests that need the views must run the
   migration, or create the views from `source_staging.*_SQL`.
   `tests/integration/test_demo_launcher_migrate.py` upgrades to head, so it will execute this
   migration.
3. **The view needs an active rule set.** B2 must insert the `source_rule_sets` row matching the
   code's versions before or at the first ingest; without one, the observation view is empty by
   design. The active row's versions should equal `IDENTITY_RULES_VERSION` /
   `NORMALIZATION_VERSION` (a B2 check).
4. **Versions, not code, identify an analysis.** `parser_build` is recorded but is not part of
   analysis uniqueness. A change in parsing semantics must bump the P1 rule versions, which is the
   existing P1 contract.
5. **CLAUDE.md is out of date.** It still names `c7f2a9b1d3e5` as head; the head is now
   `a77e01c33ee1`. CLAUDE.md was not edited.
6. **Pending gates:** G04 PostgreSQL tests are NOT_EXECUTED, and owner decisions O-2 and O-7 are
   still pending. No real ICTU import is authorized.

STOPPED after B1. B2 (ingestion service, file reader, audit events, PostgreSQL integration tests)
not started.
