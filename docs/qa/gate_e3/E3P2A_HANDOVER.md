# E3-P2-A — Source adapter and staging schema freeze: handover for owner review

Date: 2026-10-29 · Status: **P2-A DELIVERED — STOPPED FOR OWNER REVIEW** (P2-B not started)

## 1. What is implemented and what is only proposed

| Item | State |
|---|---|
| Pure adapters `backend/app/services/source_claims/adapters.py` (Craw harvest → PROFILES; guide *tables* and *rows* snapshots → SCOPUS_GUIDE) | **Implemented**, tested |
| Synthetic tests `backend/tests/unit/test_source_claims_adapters.py` (54) | **Implemented** |
| `jsonschema>=4.20` declared in `[project.optional-dependencies].dev` (`backend/pyproject.toml`, +1 line) | **Implemented**; the adapter tests import it unconditionally, so a missing install fails instead of skipping |
| Read-only run of the adapters over the real local sources | **Executed** (aggregates only; nothing written to disk or a database) |
| Source mapping | **Documented**: `E3P2A_SOURCE_MAPPING.md` |
| Staging tables, constraints, ingest outcomes, withdrawal semantics | **Proposal only**: `E3P2A_STAGING_SCHEMA_PROPOSAL.md` |
| Models, migration, ingest service, API | **Not started** (P2-B, after approval) |

The accepted E3-P1 files (`contract`, `canonical`, `parser`, `analysis`, `__init__`, the schema and
the P1 tests) are **byte-identical** to the E3-P1 closeout hashes.

## 2. Real sources (details in `E3P2A_SOURCE_MAPPING.md`)

- **`lecturers.json`** is a list of 410 profiles with 26 keys each. The e-mail field is
  `institutional_email`, not `email`.
- **The raw ORCID label ends in a link icon ("↗").** The adapter therefore uses the harvester's
  extracted iD, verifies that it is contained in the raw label, and keeps the label verbatim.
- **The file also holds birth date, gender and phone.** The adapter does not copy them (O-7).
- **The Scopus-guide page exists as two separate browser captures:** a tables snapshot (10 ambiguous
  + 59 unassigned) and a rows snapshot (34 multi-ID rows, header not captured). They become two
  artifacts with different scopes, so they are never compared with each other.

Real run, all three artifacts schema-valid:

| Artifact | Records | Keys | Claims | Completeness |
|---|---|---|---|---|
| PROFILES | 410 (304 without publications), all VALID | 410 STRONG (`source_id`) | 410 e-mail, 372 ORCID; 10 ORCID collision groups (20 profiles) | COMPLETE (410 = cards = lecturers, no drift, only a `master_thesis` failure) |
| GUIDE tables | 69 | 69 STRONG (Scopus ID) | 10 AMBIGUOUS, 59 UNASSIGNED; declared counts consistent | COMPLETE |
| GUIDE multi-ID | 34 | 34 MEDIUM (e-mail) | 83 OWNED, 34 e-mail | PARTIAL (filtered extraction, O-8) |

- Weak keys: 0.
- Owned IDs also present in the unowned lists: 0.
- Multi-ID e-mails that also appear among profile e-mails: 34/34. This is a P3 input only; no link is
  made.
- Every harvester-extracted ORCID, e-mail and name is traceable to the raw page text: 0 mismatches.

## 3. Adapter behaviour (what the tests pin down)

- **Nothing is dropped.**
  - Every item becomes one record, in source order, including profiles without publications and
    malformed items (a non-object profile, missing e-mail, non-text ORCID); the parser flags them.
  - Upstream problems the contract cannot represent raise `AdapterError` with a code. Examples: an
    unclassified profile field (fail-closed), an unresolvable or duplicated table kind, a missing header
    row, a declared count for a table that is not in the capture, a snapshot whose stated row count
    differs from its rows, an origin that is not an http(s) URL with a host, and invalid hashes.
- **Content versus capture:**
  - Retrieval times, snapshot hashes, harvester diagnostics and adapter or projection versions go to
    `capture`.
  - Identical source content therefore gives an identical `content_hash` (the input for REUSED), and
    a re-capture changes only `capture_hash`.
  - Reordered JSON keys give identical artifact bytes.
- **Identity:** keys come only from `source_id`, e-mail, a Scopus ID or the content hash; a name is
  never a key. Duplicate ORCID, e-mail and Scopus-ID claims are all kept and reported. Adapter output
  contains no identity-decision field.
- **Completeness:**
  - Profiles: computed from manifest and crawl-report evidence. Missing cards, drift, a lecturer
    entity failure or an absent report all give PARTIAL.
  - Guide: completeness is an explicit argument.
  - PARTIAL captures never produce WITHDRAWN (tested for profiles and guide). Reclassification
    AMBIGUOUS → UNASSIGNED between comparable captures is reported as RECLASSIFIED.
- **Artifact origin is stricter than profile IDs** (reviewer boundary 5): artifact `source_url` must be
  an http(s) URL with a host. Opaque identifiers remain allowed for profile `source_id`, as P1 accepted.
- **Purity:** importing `adapters` loads no forbidden module (measured as a `sys.modules` delta under
  `python -I -S`).

## 4. Owner-design questions O-1 … O-6 (and two new ones)

| # | Recommendation | Owner action? |
|---|---|---|
| O-1 Content vs capture | Three layers: `source_contents` (unique `content_hash`), `source_captures` (unique `content_id, capture_hash`) and `source_analyses` (unique per content × rule versions). Records and claims hang off the *analysis*, so a rule change re-analyses instead of reusing old claims. | Confirms the owner's stated direction; approve with the P2-B migration |
| O-2 Original artifact ownership/storage | The canonical artifact needs **no blob**. Its exact bytes are rebuilt from `content_json` + `capture_json` (verified on all three real artifacts), and `artifact_bytes_sha256` is stored. The *upstream* raw files (`lecturers.json` with personal data, browser snapshots) stay **outside Git** in a restricted local store, referenced by SHA-256 and `upstream_storage_ref`. | **Yes**: choose the retention location and period for upstream raw files |
| O-3 Normalization contract | Keep the P1 rules unchanged and versioned. E-mail and URL are source-identity signals, not verification of a person. | No |
| O-4 `EMAIL_DECLARED` for multi-ID rows | Keep. The real data shows it is the bridge for P3 (34/34 rows match a profile e-mail), and it stays evidence, not approval. | No (already accepted) |
| O-5 Actual `lecturers.json` mapping | Resolved and implemented: `institutional_email` → `email`, harvester `orcid` with the raw label verified, `source_id` URL as the STRONG key, allowlisted raw labels. | No |
| O-6 Weak-key records | Never auto-linked and never treated as withdrawn (`KEY_UNSTABLE`). The real data has **0** weak-keyed records; if any appear, they go to a manual P3 queue. | No |
| **O-7 (new)** Personal-data minimization | Do not stage birth date, gender or phone (excluded and counted). Staging is ADMIN-readable only. | **Yes**: approve the exclusion policy |
| **O-8 (new)** Multi-ID capture completeness | Keep the existing rows snapshot as PARTIAL. Before relying on multi-ID withdrawal, recapture the whole page once, with headers and all three tables. | No (recommendation; the capture-tool change belongs to a later capture) |

Still open from E3-P1, and out of scope here: the tracked `docs/qa/gate_d1r/ictu_*.csv` files contain
names and e-mails.

## 5. Verification

| Check | Result |
|---|---|
| Adapter tests (`--noconftest`) | **54 passed** |
| E3-P1 + adapter suites together | **172 passed**, 0 skipped, 0 xfailed |
| Focused set (replay, reorder, ORCID, duplicate IDs, missing profiles, partial, reclassified, discrepancy, malformed) | 36 passed |
| Ruff (`app/services/source_claims`, both test files) | exit 0 |
| Real-data run: schema-valid, re-encode stable, deterministic over 4 `PYTHONHASHSEED` values | yes / yes / one digest |
| `E3P2A_IMPLEMENTATION.diff` replayed on the accepted P1 tree (P1 → errata → closeout → P2-A, `--whitespace=error`) | 3/3 files reproduce the workspace; reverse check OK; whitespace clean |
| E3-P1 files vs closeout hashes | 7/7 unchanged |
| G01–G04: 31 recorded files | 31/31 MATCH |
| `git status` | the session-start set (15 files) plus `backend/pyproject.toml`; no alembic, model, API or frontend change |

`backend/pyproject.toml` is CRLF in the working tree (`core.autocrlf=true`). Its diff and hash are
reported on the LF form Git stores.

## 6. Limitations and boundaries

- The project `conftest.py` needs an allowlisted test DB, so the tests ran with `--noconftest`. No
  database was used.
- The real run used local, untracked inputs: Craw output and the Gate D3/D4 snapshots. Their personal
  values were never copied into tests, documents or the repository.
- The guide's declared counts (10, 59) are a transcription of the captured summary text, which the
  capture tool partly paraphrased. The "35" multi-ID total is kept in that text only (see the source
  mapping, §3).
- CLAUDE.md states the migration head as `c7f2a9b1d3e5`; the actual single head is `a1b2c3d4e5f6`.
  CLAUDE.md was not edited (out of scope).
- G04 PostgreSQL isolation tests remain **NOT_EXECUTED**. No real-data database ingest is authorized
  until they pass.

## 7. Files

- New: `backend/app/services/source_claims/adapters.py`,
  `backend/tests/unit/test_source_claims_adapters.py`.
- Modified: `backend/pyproject.toml` (+1 dev dependency).
- Documents: `E3P2A_HANDOVER.md`, `E3P2A_SOURCE_MAPPING.md`, `E3P2A_STAGING_SCHEMA_PROPOSAL.md`,
  `E3P2A_IMPLEMENTATION.diff`, `E3P2A_TEST_RESULTS.txt`, `E3P2A_VALIDATION.json`.

No commit, push, migration or database write. STOPPED after P2-A.
