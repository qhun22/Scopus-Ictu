# E3-P2-A — Staging schema proposal (design freeze, not implemented)

Status: **REVISED PROPOSAL (rev. 2, P2A-S1 correction) FOR INDEPENDENT REVIEW.** No model,
migration or database object was created. P2-B implements this only after approval.

**Rev. 2 (2026-10-29), P2A-S1.** Rev. 1 stored only `contract_major` and made captures unique on
`(content_id, capture_hash)`. Two artifacts that differ only in `contract_version` (1.0 vs 1.1)
have the same content and capture hashes but different bytes, so rev. 1 would have collapsed them
and could not rebuild either one exactly.

Rev. 2 separates three things:
- **capture identity**: one observation, `source_captures`;
- **artifact identity**: one exact envelope, the new `source_artifacts` table, `UNIQUE
  (artifact_bytes_sha256)`, which stores the exact `contract_version`;
- **analysis identity**: an analysis is keyed by contract version, and each artifact references
  the analysis of its own version.

The changed parts are §2.2, §2.2a, §2.3, §2.6 and §3. The keys are defined once, in
`adapters.staging_keys()` and `adapters.reconstruct_artifact_bytes()`, and a regression test
covers them.

## 1. Principles carried over from E3-P1

1. **Content is not capture.** The source assertion (`content_hash`) is stored once. Every
   observation of it (`capture_hash`, time, completeness) is a separate row. Each exact envelope
   of an observation (contract version included) is a separate artifact row (rev. 2).
2. **Analyses are versioned.** Records and claims are derived from a content *under specific rule
   versions*. A rule change produces a new analysis and never reuses claims parsed by older logic
   (owner constraint on O-1).
3. **Duplicates are evidence.** Two records may share a key and two claims may assert the same
   value. Nothing is UNIQUE on `record_key` or on `claim_key` alone.
4. **Append-only.** No UPDATE or DELETE on staging rows. This is the existing convention, M1.0-A08:
   no `updated_at` column.
5. **Claims are never identities.** No staging table references `lecturers`,
   `lecturer_scopus_identities`, candidates or reviews. P3 reads staging; staging reads nothing
   downstream.

## 2. Tables

The SQL is indicative. Constraint names follow the repository's FC-01 naming convention. All hash
columns carry the existing `CHECK (col ~ '^[0-9a-f]{64}$')` pattern.

### 2.1 `source_contents`: immutable source assertion
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | `gen_random_uuid()` |
| `source_system` | varchar(50) | CHECK IN (`ICTU_REPO_SCOPUS_GUIDE`, `ICTU_REPO_PROFILES`) |
| `contract_major` | smallint | CHECK = 1 |
| `scope_key` | char(64) | what was captured (source, origin URL, tables) |
| `source_url` | text | artifact origin, http(s) with a host (adapter-enforced) |
| `content_hash` | char(64) | `sha256(content_json)` |
| `content_json` | text | canonical JSON exactly as hashed; CHECK `encode(sha256(convert_to(content_json,'UTF8')),'hex') = content_hash` |
| `created_at` | timestamptz | first time this content was seen |

- `UNIQUE (source_system, content_hash)` gives REUSED detection.
- `UNIQUE (id, source_system)` is the parent key for the composite FK in 2.2.
- `INDEX (source_system, scope_key)`.

`content_json` is TEXT, not JSONB. Byte-exact text lets the database itself re-verify the hash, which
JSONB's re-serialization would not allow.

### 2.2 `source_captures`: one observation of one content
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `content_id`, `source_system` | uuid, varchar(50) | composite FK → `source_contents(id, source_system)` ON DELETE RESTRICT |
| `captured_at` | timestamptz | from the capture block |
| `completeness` | varchar(10) | CHECK IN (`COMPLETE`, `PARTIAL`); for profiles, the adapter's fail-closed rule (§4) |
| `capture_hash` | char(64) | |
| `capture_json` | text | canonical; CHECK sha256 = `capture_hash` |
| `adapter_version`, `projection_version` | varchar(100) | copied from `capture_json` (comparability input) |
| `upstream_name`, `upstream_bytes_sha256` | text, char(64) | copied from `capture_json` (lineage) |
| `created_at` | timestamptz | first time this observation was seen |

- `UNIQUE (content_id, capture_hash)`. This is now correct, because a capture is a pure
  observation: artifacts that differ only in contract version share one capture and one
  observation time.
- `UNIQUE (id, content_id)` is the parent key for 2.2a.
- `INDEX (source_system, captured_at)` and `INDEX (content_id)`.

### 2.2a `source_artifacts`: one exact artifact envelope (new in rev. 2)
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `content_id` | uuid | |
| `capture_id` | uuid | composite FK (`capture_id`, `content_id`) → `source_captures(id, content_id)` RESTRICT |
| `contract_version` | varchar(20) | **exact** version, CHECK `contract_version ~ '^1\.[0-9]+$'` (PostgreSQL ARE: `$` is end of string, so this matches the parser's `fullmatch`) |
| `analysis_id` | uuid | composite FK (`analysis_id`, `content_id`, `contract_version`) → `source_analyses(id, content_id, contract_version)`: an artifact can only use an analysis of its own content and version |
| `artifact_bytes_sha256` | char(64) | SHA-256 of the canonical artifact bytes; **`UNIQUE`**: the artifact identity |
| `received_bytes_sha256` | char(64) NULL | set when the artifact arrived as a file whose bytes were not canonical (P2-B stores the canonical form) |
| `upstream_storage_ref` | text NULL | where the raw upstream file is retained (O-2), never a repository path |
| `ingested_by` | uuid NULL | FK → `users(id)` RESTRICT; NULL for a SYSTEM actor |
| `ingested_at` | timestamptz | `now()` |

- `INDEX (capture_id)` and `INDEX (content_id, contract_version)`.
- **Byte-exact reconstruction, no blob:**
  `adapters.reconstruct_artifact_bytes(source_system, artifact.contract_version,
  capture.capture_json, content.content_json)` re-hashes to `artifact_bytes_sha256`. P2-B checks this
  on every ingest, and an integrity query can re-check it at any time. It was verified on all three
  real artifacts.
- The regression test shows that the bytes rebuilt with the *other* minor version hash to the other
  artifact. The version therefore has to be stored per artifact, and it is never inferred from
  `source_contents` or `source_analyses`.
- `adapters.staging_keys()` refuses an artifact whose bytes are not canonical
  (`ARTIFACT_NOT_CANONICAL`), so no stored hash can describe bytes that cannot be rebuilt.

### 2.3 `source_analyses`: one parse of one content under one rule set
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `content_id` | uuid | FK RESTRICT |
| `contract_version`, `identity_rules_version`, `normalization_version` | varchar(20) | from `ParsedSnapshot` |
| `parser_build` | varchar(100) | code identifier of the parser that produced the analysis |
| `artifact_issues` | jsonb | CHECK `jsonb_typeof = 'array'` |
| `declared_counts` | jsonb | CHECK `jsonb_typeof = 'object'` |
| `record_count`, `claim_count` | int | CHECK ≥ 0; must equal the child row counts (verified in service) |
| `created_at` | timestamptz | |

- `UNIQUE (content_id, contract_version, identity_rules_version, normalization_version)`.
- `UNIQUE (id, content_id)` is the parent key for 2.4, and `UNIQUE (id, content_id,
  contract_version)` is the parent key for 2.2a.
- One content can have several analyses: other minor versions, or later rule versions. The
  analysis therefore never answers "which contract version was this artifact"; the artifact row
  does.

### 2.4 `source_records`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `analysis_id` | uuid | FK RESTRICT |
| `record_kind` | varchar(30) | CHECK IN (`PROFILE`, `MULTI_ID_ROW`, `AMBIGUOUS_ID_ROW`, `UNASSIGNED_ID_ROW`) |
| `source_position` | int | CHECK ≥ 1 |
| `record_hash` | char(64) | position excluded |
| `record_key`, `key_method`, `key_strength` | text, varchar(30), varchar(10) | CHECK vocabularies; `key_strength` IN (`STRONG`, `MEDIUM`, `WEAK`) |
| `raw` | jsonb | the record's raw source value (any JSON type: a malformed row may be a string) |
| `normalized` | jsonb | CHECK `jsonb_typeof = 'object'` |
| `validation_status` | varchar(10) | CHECK IN (`VALID`, `WARNING`, `INVALID`) |
| `issues` | jsonb | CHECK array |

- `UNIQUE (analysis_id, record_kind, source_position)`.
- `UNIQUE (id, analysis_id)` is the parent key for 2.5.
- **No unique constraint on `record_key`.** Duplicate keys are kept and flagged
  (`DUPLICATE_RECORD_KEY`).
- `INDEX (analysis_id, record_kind, record_key)`, `INDEX (record_hash)`, and
  `INDEX (key_method, record_key)` for P3 lookups.

`raw` can be JSONB here: `record_hash` covers `canonical_json({"record_kind", "raw"})`. Canonical JSON
sorts keys and has no floats, so the hash is reproducible from JSONB. The content-level TEXT column
remains the byte-exact authority.

### 2.5 `source_claims`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `analysis_id`, `record_id` | uuid | composite FK → `source_records(id, analysis_id)` |
| `claim_type` | varchar(30) | CHECK IN the 5 `ClaimType` values |
| `subject_key` | text NULL | CHECK: NULL **iff** `claim_type` IN (`SCOPUS_ID_AMBIGUOUS`, `SCOPUS_ID_UNASSIGNED`) |
| `value_raw`, `value_normalized`, `value_method` | text, text NULL, varchar(60) | |
| `value_valid` | boolean | generated: `value_normalized IS NOT NULL` |
| `claim_key` | text | `TYPE|subject|value` |
| `flags` | jsonb | CHECK object (`is_primary_claimed`, `listed`, `subject_key_strength`, …) |

- `UNIQUE (record_id, claim_key)`. One record never asserts the same claim twice; the parser already
  de-duplicates within a row.
- **Not unique:** `claim_key` per analysis or globally. In the real data, 20 profiles declare 10
  shared ORCIDs, and the same e-mail is asserted by the profile source and by the multi-ID row. Each
  assertion keeps its own provenance, through `record_id → analysis → artifacts → captures`.
- `INDEX (claim_type, value_normalized)` for "who asserts this ID or ORCID", plus
  `INDEX (analysis_id, claim_key)` and `INDEX (subject_key)`.

### 2.6 Claim observations: a view, not a table
`source_claim_observations` (VIEW) gives one row per (capture, claim), with `captured_at` and
`completeness`. It joins `source_captures → source_artifacts → source_analyses → source_claims`,
choosing, per capture, the analysis under the current rule versions.

The view is keyed by **capture**, not by artifact. Two artifacts of one capture (e.g. 1.0 and 1.1)
therefore count as one observation, so withdrawal and frequency analysis never double-count.

Materializing a row per claim per capture would write 782 rows for every identical re-capture of
the profiles, and add no information: the capture → content link already proves observation.
Materialize only if P3 query plans need it.

## 3. Ingest semantics (P2-B service)

All of these steps run in one transaction:
1. Run the adapter, compute `artifact_bytes`, call `parse_artifact_bytes`, then compute
   `adapters.staging_keys` (pure; no write if any step raises).
2. If `artifact_bytes_sha256` already exists in `source_artifacts`, the outcome is
   `ALREADY_INGESTED`: write the audit event only, then stop.
3. `INSERT content … ON CONFLICT (source_system, content_hash) DO NOTHING RETURNING id`. On
   conflict, select the existing row.
4. Insert the analysis for (content, contract version, current rule versions) `ON CONFLICT DO
   NOTHING`. Only when it is new, bulk-insert its records and claims, then verify the counts.
5. `INSERT capture … ON CONFLICT (content_id, capture_hash) DO NOTHING`, then select its id.
6. `INSERT artifact …` with `contract_version`, `analysis_id` and `artifact_bytes_sha256`.
   `UNIQUE(artifact_bytes_sha256)` makes a concurrent duplicate fail and retry as
   `ALREADY_INGESTED`.
7. Rebuild the artifact bytes from the stored rows and compare them with
   `artifact_bytes_sha256`. A mismatch aborts the transaction.
8. Write one `audit_events` row: `entity_type = 'source_artifact'`,
   `action = 'SOURCE_ARTIFACT_INGESTED'`, and in metadata the outcome, the content, capture and
   artifact hashes, the contract version and the counts.

| Outcome | Condition | Rows written |
|---|---|---|
| `CREATED` | new `content_hash` | content + analysis + records + claims + capture + artifact |
| `REUSED` | known content, new `capture_hash` | capture + artifact (+ analysis if this minor version has none yet) |
| `ARTIFACT_ADDED` | known capture, new artifact (e.g. another contract minor version) | artifact (+ analysis for that version if new) |
| `REANALYSED` | known content, new rule versions | analysis + records + claims, plus any new capture or artifact |
| `ALREADY_INGESTED` | known `artifact_bytes_sha256` | none (audit event only) |

Regression (`test_proposed_unique_keys_keep_both_contract_versions`): ingesting 1.0, 1.1 and 1.0
again gives 1 content, 1 capture and 2 artifacts. Rev. 1's capture key would have kept 1.

The unique constraints keep concurrent ingests idempotent. No step touches reviewer decisions,
candidates or identities.

## 4. Versioning and withdrawal

- **Completeness is fail-closed (P2A-S2).** For profiles, the adapter marks a capture COMPLETE only
  when every one of the following holds:
  - the harvest status is one the harvester writes for success (`COMPLETE`, or
    `COMPLETE_WITH_SOURCE_FAILURES`), and it agrees with the failure list;
  - the run's `semantic_replay.json` passed (`a_equals_b_equals_c`) and replayed this exact
    `lecturers.json`;
  - the card and lecturer counts match;
  - there is no drift and no `lecturer` failure.

  Anything unknown, missing or inconsistent gives PARTIAL. A failure of another entity, such as
  `master_thesis`, does not affect the profile listing.
- **Comparability.** Two captures are compared only when all of the following hold:
  - same `source_system` and `scope_key`;
  - both COMPLETE;
  - in chronological order;
  - same contract major, identity-rules and normalization versions (P1 `comparability`);
  - same `projection_version`. This is a new capture-level condition: a projection change alters the
    content without any change in the source.
- **Withdrawal is derived, never stored as a mutation.** `presence_diff(previous, current)` runs on
  demand. A withdrawn claim keeps all its rows. Absence in a PARTIAL or non-comparable capture is
  `NOT_OBSERVED`, and absence of a WEAK key is `KEY_UNSTABLE`.
- Persisting diff results is deferred to P3, and only if a reviewer workflow needs to act on them.
- **Rule changes:** bump the version and re-analyse (`REANALYSED`). Old analyses stay for audit.
  "Current" means matching the running code's versions.

## 5. Comparison with existing tables (no duplication)

| Existing | Why it is not reused | What is reused |
|---|---|---|
| `lecturer_source_snapshots` | keyed to `lecturer_id`; one payload per lecturer from the lecturer-dataset import. Staging claims must exist *before and without* identity. | conventions: hash CHECKs, JSONB type CHECKs, append-only, RESTRICT FKs |
| `scopus_imports` / `raw_scopus_records` | Scopus CSV pipeline with a mutable status machine (`RECEIVED…APPLIED`, optimistic lock). Staging ingest is one atomic transaction with no intermediate states. | header + raw rows + `UNIQUE(import_id, row_number)` pattern (mirrored as `UNIQUE(analysis_id, kind, position)`) |
| `audit_events` | — | **reused** for ingest audit; no new audit table |
| candidates, reviews, `lecturer_scopus_identities`, `identity_evidence` | downstream (P3+); untouched | P3 reads `source_claims` to produce candidate evidence |

## 6. Expected volumes (real data, one capture each)

| Content | Records | Claims |
|---|---|---|
| PROFILES | 410 | 782 |
| GUIDE tables | 69 | 69 |
| GUIDE multi-ID | 34 | 117 |

Measured `content_json` sizes are 482 kB, 4.0 kB and 3.9 kB. A REUSED re-capture adds one
capture row only: 408 kB of `capture_json` for profiles (the per-profile observations), and under
1 kB for each guide capture.

## 7. Access and personal data

- `content_json` holds names, institutional e-mails and ORCIDs (public profile data). Birth date,
  gender and phone are excluded by the adapter (O-7).
- Staging tables should be readable by ADMIN only. Any future API exposes aggregates or single
  records to ADMIN or REVIEWER, never to LECTURER.

## 8. For P2-B

- The migration chain currently has a single head, `a1b2c3d4e5f6`
  (`m5_enrichment_resume`). This was checked statically from the revision files; **CLAUDE.md's
  "current head `c7f2a9b1d3e5`" is out of date.** Re-check with `alembic heads` at P2-B time.
- Deliver one append-only revision creating §2.1–2.5 (including §2.2a) and the §2.6 view, with a
  full `downgrade`.
- Before any real ingest: complete the G04 PostgreSQL isolation tests, then the P2-B integration tests
  on an allowlisted disposable database.
