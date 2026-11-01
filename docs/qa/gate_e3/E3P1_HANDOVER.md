# Gate E.3 / P1 — Source-claim contracts and provenance (pure)

Date: 2026-10-29. Status: **IMPLEMENTED; READY FOR INDEPENDENT REVIEW.**
Scope: in-memory contracts, parsing, canonicalization, provenance and analysis only.
No database model, migration, endpoint, frontend, real data, reviewer action, commit or push.

## 1. Preservation check

- `git status` before and after: the existing modified set is unchanged. G04's four files and its
  two hashed artifacts re-hash to the values in `G04_VALIDATION.json` (all MATCH).
- **New paths only:**
  - `backend/app/services/source_claims/` (5 files);
  - `backend/tests/unit/test_source_claims.py`;
  - `data/source_claims/schema/ictu_source_claims.schema.json`.

  No existing file was edited.

## 2. Files

| File | Lines | Purpose |
|---|---|---|
| `source_claims/__init__.py` | 7 | Package docstring; imports nothing. |
| `source_claims/contract.py` | 257 | Versions (`CONTRACT_VERSION 1.0`, `IDENTITY_RULES_VERSION 1`, `NORMALIZATION_VERSION 1`), `StrEnum` vocabularies, frozen value types. |
| `source_claims/canonical.py` | 199 | Strict canonical JSON, SHA-256, normalizers (Scopus ID, ORCID with checksum, e-mail, name, profile source_id, counts, ID-list split). |
| `source_claims/parser.py` | 557 | Envelope validation, both source systems, records, keys, claims, duplicate-key flags, declared-count checks. |
| `source_claims/analysis.py` | 327 | ORCID/e-mail collision groups, Scopus ID collisions, declared vs actual, distinct-ID counts, comparability, presence diff. |
| `data/source_claims/schema/ictu_source_claims.schema.json` | 117 | Versioned artifact contract (documentation; kept in sync by a test). |
| `tests/unit/test_source_claims.py` | 618 | 58 synthetic tests. |

**Purity (requirement D):** the package imports only the standard library and itself.
- `candidate_persistence.canonical_json` was **not** imported: that module loads SQLAlchemy and
  the ORM models. A strict equivalent with the same settings was written instead (sorted keys,
  compact separators, UTF-8; it additionally rejects floats and non-JSON types).
- `lecturer_dataset.parser` was **not** imported: the package `__init__` loads the ORM importer. Its
  e-mail regex shape is reproduced.
- Importing `app.services` itself loads only two stub modules (measured: no SQLAlchemy).

## 3. Artifact contract (input)

```json
{"contract": "ictu-source-claims", "contract_version": "1.0",
 "source_system": "ICTU_REPO_SCOPUS_GUIDE",
 "capture": {"captured_at": "2026-10-29T00:00:00Z", "completeness": "COMPLETE", "...": "free metadata"},
 "content": {"source_url": "...",
   "page_summary": {"text": "<raw text>", "declared_counts": {"MULTI_ID_LECTURERS": 35}},
   "tables": {"MULTI_ID":   {"heading": "...", "columns": [{"header": "<as published>", "role": "NAME"}, "..."], "rows": [["cell", "..."]]},
              "AMBIGUOUS":  {"...": "roles SCOPUS_NAME, SCOPUS_ID (required), DECLARED_PUB_COUNT, OTHER"},
              "UNASSIGNED": {"...": "same roles as AMBIGUOUS"}}}}
```

**Column roles:** the artifact declares what each column means, so published headers stay
verbatim. MULTI_ID roles are NAME, EMAIL, DECLARED_ID_COUNT, DECLARED_PUB_COUNT,
PRIMARY_SCOPUS_ID, SCOPUS_ID_LIST (required) and OTHER.

`ICTU_REPO_PROFILES` content is `{"source_url", "declared_counts": {"PROFILES": n}, "profiles": [...]}`.
- Every profile object is kept verbatim, including those without publications.
- `source_id`, `email`, `orcid` and `full_name` have defined meanings.

**Envelope violations raise `ArtifactError` with a code.** These include: wrong contract or major
version, unknown source system, unknown fields, missing `captured_at` or UTC offset, invalid
completeness, unknown table, invalid column role, floats, and (bytes input) duplicate JSON keys
or non-UTF-8 data.

**Problems inside a row or profile never drop it.** They become issues on a kept record
(ERROR → `INVALID`, WARNING → `WARNING`).

### Output example (synthetic, built with the test-suite helpers)

Input: one MULTI_ID row `["GV A", "A@Example.invalid", "3", "3", "57000000002", "57000000001; 57000000002"]`
(declares 3 IDs, lists 2), and one UNASSIGNED row `["Y. Synthetic", "57000000002", "2"]`. The page
summary declares `MULTI_ID_LECTURERS: 2`.

```
snapshot issue  SOURCE_COUNT_MISMATCH  "Source declares MULTI_ID_LECTURERS=2 but its detailed listing has 1."
record MULTI_ID_ROW#1     key a@example.invalid (EMAIL_V1, MEDIUM)  WARNING  [ID_COUNT_MISMATCH]
record UNASSIGNED_ID_ROW#1 key 57000000002 (SCOPUS_ID_V1, STRONG)   VALID
claim EMAIL_DECLARED       EMAIL_DECLARED|a@example.invalid|a@example.invalid  raw 'A@Example.invalid'
claim SCOPUS_ID_OWNED      SCOPUS_ID_OWNED|a@example.invalid|57000000001  listed, is_primary_claimed=False
claim SCOPUS_ID_OWNED      SCOPUS_ID_OWNED|a@example.invalid|57000000002  listed, is_primary_claimed=True
claim SCOPUS_ID_UNASSIGNED SCOPUS_ID_UNASSIGNED|-|57000000002  (no subject: never attributed)
analysis: scopus_id_collisions -> 57000000002 CROSS_TABLE (owned + unassigned)
```

## 4. Hashing and idempotency (requirement A)

| Concept | Definition | Changes when |
|---|---|---|
| Original artifact bytes | `artifact_bytes_sha256`, only via `parse_artifact_bytes` | any byte changes (whitespace, key order) |
| Semantic source payload | `content`, kept as canonical JSON (`content_json`, recoverable via `.content`) | — |
| Source content hash | `content_hash = sha256(canonical_json(content))` | the source assertion changes |
| Capture metadata | `capture` block → `capture_json`, `capture_hash`; `captured_at` and `completeness` parsed out | capture time, tool, notes or completeness change |
| Scope key | `sha256({contract_major, source_system, normalized source_url, captured tables / "profiles"})` | a different page or table set is captured |
| Record hash | `sha256({record_kind, raw value})`; position excluded, position kept separately | that row/profile's raw value changes |
| Claim key | `CLAIM_TYPE|subject|value`, value = normalized, or `raw-sha256:<hash>` when invalid | type, subject or value changes |

Guarantees, each tested:
- **Capture time does not change the content hash:** changing only `captured_at` (or adding capture
  metadata) gives the same `content_hash`, records and claims, and a different `capture_hash`.
- **Key order and whitespace do not change it:** reordered keys and different whitespace give the
  same `content_hash`. The bytes hash differs, so byte identity stays a separate fact.
- **Hashes cover raw values, never normalized ones:** `0000-0002-1825-0097` and
  `https://orcid.org/0000-0002-1825-0097` normalize alike but give different content and record
  hashes, and both raw spellings are preserved.
- **Floats are rejected**, so number formatting can never alter identity.
- **Byte-exact boundary (documented):**
  - A parsed `dict` cannot prove byte-exact content, so `parse_artifact(dict)` reports
    `artifact_bytes_sha256 = None`.
  - Byte-exact preservation of the artifact file is the caller's job (store the file; P2).
  - The original HTML page is upstream of the artifact. Only its optional `capture.raw_html_sha256`
    is carried.
- **REUSED vs new version:** identical content means an identical `content_hash`. P2 must use this
  for `REUSED` instead of writing new rows (see decision O-1).

## 5. Record identity and collisions (requirement B)

| Record | Key, in order of preference | Method | Strength |
|---|---|---|---|
| PROFILE | normalized `source_id` (URL: scheme/host lower-case, default port, fragment and trailing `/` removed; path/query kept) | `PROFILE_SOURCE_ID_V1` | STRONG |
| PROFILE / MULTI_ID_ROW | normalized e-mail (NFKC, trim, casefold) | `EMAIL_V1` | MEDIUM |
| AMBIGUOUS / UNASSIGNED row | the row's valid Scopus ID | `SCOPUS_ID_V1` | STRONG |
| any, otherwise | `content:<record_hash>` (source-scoped, deterministic) | `CONTENT_V1` | WEAK |

- **Names are never keys.** A normalized name is kept only as a lookup signal. Two
  "Nguyễn Văn Nam" rows remain two records, keyed by e-mail or by content.
- **Duplicate keys** inside one snapshot are flagged on **every** record that shares them:
  `DUPLICATE_RECORD_KEY`, or `DUPLICATE_SOURCE_ROW` for identical content. All records are kept;
  nothing is merged, renamed or overwritten. In a presence diff such a key reports `KEY_COLLISION`.
- The key method and strength are stored with every key, so a later rule change is detectable.

## 6. Completeness and withdrawal (requirement C)

`comparability(previous, current)` requires all of the following:
- same source system (otherwise `ValueError`);
- both COMPLETE;
- same `scope_key`;
- same contract major;
- same identity-rules and normalization versions;
- chronological order.

Any failing condition is listed in `reasons`.

| Situation | Status |
|---|---|
| absent now, comparable, strong/medium key | `WITHDRAWN` |
| absent now, not comparable (PARTIAL, other scope, other rules, out of order) | `NOT_OBSERVED` |
| absent now, WEAK content key | `KEY_UNSTABLE` (a changed cell, not proof of removal) |
| Scopus ID moved between categories (e.g. UNASSIGNED → OWNED) | `RECLASSIFIED`, with before/after labels |
| owned ID now owned by another strong/medium-keyed row | `OWNER_CHANGED` |
| owner keys weak | `OWNER_UNVERIFIABLE` |
| same key, different content / declared value | `CHANGED` |
| key duplicated in either snapshot | `KEY_COLLISION` |

- **Dimensions are kept apart:** `RECORD:PROFILE`, `RECORD:MULTI_ID_ROW`, `SCOPUS_ID`,
  `ORCID_DECLARED`, `EMAIL_DECLARED`. Claim types and tables are never conflated.
- **Immutability:** every output is a frozen dataclass with tuple collections, and raw values are
  stored as JSON text. `presence_diff` is tested not to modify its inputs, and attribute assignment
  raises an error.

## 7. Source assertions are kept, not corrected

- **Declared counts:** the page's declared counts are kept (`declared_counts`), and a mismatch is
  reported as `SOURCE_COUNT_MISMATCH`. Tested: 35 declared vs 34 rows keeps 34 records and
  `declared = 35`.
- **Primary IDs are flags only:** `is_primary_claimed`. A primary ID missing from the row's list
  is kept as an unlisted claim with `PRIMARY_NOT_IN_LIST`.
- **Unowned IDs have no subject:** AMBIGUOUS/UNASSIGNED claims have `subject_key = None`.
  Nothing attributes them.
- **No identity semantics:** claim and record types carry no lecturer, author, status or decision
  field (tested).

## 8. Tests and evidence

| Check | Result |
|---|---|
| `tests/unit/test_source_claims.py` under the purity guard | **58 passed**, exit 0, forbidden modules loaded `[]` |
| Fresh `python -I` import of parser + analysis | none of SQLAlchemy, psycopg2, FastAPI, settings, `app.main`/`core`/`models`/`api`, HTTP clients, socket |
| Cross-process replay, `PYTHONHASHSEED` 0 / 1 / 4242 / random | identical digest `dc10a1d1…ef24` |
| Mutation probes (capture in content hash; withdraw without comparability; unsorted canonical JSON; keys silently made unique) | **4/4 detected** (1, 5, 1, 10 failing tests) |
| Ruff on all new files | All checks passed; 0 new diagnostics, since no existing file changed |
| Scoped diff | 7 new-file diffs, `git apply --check -R` OK |

**TC-SC mapping (pure scope):**
- 01–02 ORCID collisions;
- 03 three IDs + primary + count mismatch;
- 04 cross-table;
- 05 multi-owner;
- 06 unowned never attributed;
- 07 absent owner stays an unresolved claim;
- 08 shared e-mail;
- 09 identical parse;
- 10 withdrawn;
- 11 reclassified;
- 12 PARTIAL;
- 13 35 vs 34;
- 14 invalid raw preserved;
- 15 profiles without publications;
- 17 Unicode/whitespace normalization.

**TC-SC-16** (ID not in `scopus_authors`) needs the database and is **out of P1 scope**; it belongs
to P3 resolution.

**Additional tests:**
- capture-time change; reordered keys and whitespace; same-name records; duplicate keys;
- raw values that normalize alike; COMPLETE/PARTIAL; scope, out-of-order and rules-version
  changes; weak-key absence; owner change;
- envelope and byte-level violations; lossless reconstruction; schema/code sync.

All fixtures are synthetic:
- `example.invalid` domains;
- fake 570000000xx Scopus IDs;
- ORCID documentation example iDs.

## 9. Decisions needing owner approval

1. **O-1 — P2 storage of versions vs captures.** Requirement A separates content from capture,
   which changes the earlier 4-table proposal:
   - store `source_claim_contents` (unique `source_system, content_hash`; records and claims hang
     here, written once);
   - plus `source_claim_captures` (each observation: `captured_at`, completeness, capture_hash,
     artifact bytes hash; unique `content_id, capture_hash`).

   An identical artifact gives `REUSED`. The same content captured later adds one capture row and
   no records, which still lets "re-confirmed at time t" count toward COMPLETE comparisons.
2. **O-2 — Who produces artifacts.** Declared counts are a capture-tool reading of the page text,
   with the raw text kept. P2 needs an offline capture script and a place to keep raw HTML/JSON
   files outside the repository.
3. **O-3 — Normalization choices** (all versioned):
   - e-mail casefolded entirely, local part included;
   - ORCID with a failed check digit is INVALID, not normalized;
   - Scopus IDs are 6–15 digits;
   - profile URL path/query keep their case.
4. **O-4 — `EMAIL_DECLARED` is also emitted for MULTI_ID rows** (the owner's e-mail as a source
   assertion), not only for profiles.
5. **O-5 — Real `lecturers.json` field names were assumed** from the Craw contract
   (`source_id`, `full_name`, `email`, `orcid`). They are not verified against the real file;
   P1 read no real data. A read-only field check belongs to P2.
6. **O-6 — Weak-keyed rows** (no e-mail) report `KEY_UNSTABLE`/`OWNER_UNVERIFIABLE` instead of
   withdrawal. If the source has such rows, P3 may need a manual linking step.
7. **Still open from E.3:** three tracked `docs/qa/gate_d1r/*.csv` files contain names/e-mails
   (data policy).

**Dependency status:** P1 does not depend on G04. G04 PostgreSQL acceptance is still pending and
still gates P2/P3 acceptance.

STOPPED after E3-P1. E3-P2 not started.
