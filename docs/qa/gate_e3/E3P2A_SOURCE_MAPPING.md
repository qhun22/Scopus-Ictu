# E3-P2-A — Source mapping (real structures → E3-P1 contract)

Date: 2026-10-29. Read-only inspection of the local sources. This document reports field
names, counts, shapes and hash prefixes only. No name, e-mail, ORCID, phone, birth date or
personal Scopus ID is reproduced here.

## 1. Source inventory and lineage

| Upstream | Location (not in Git) | Size / count | SHA-256 (exact bytes) | Observed | Becomes |
|---|---|---|---|---|---|
| Craw harvest `lecturers.json` | `CRAW_SOURCE_DIR` (`…/Craw/output/full`) | 410 items, 1.73 MB | `c12252e0…` | profiles retrieved 2026-10-03 18:44–20:09Z; harvest run 20:05–21:31Z | `ICTU_REPO_PROFILES` artifact |
| `harvest_manifest.json` | same | 1 object | — | harvest metadata | capture metadata + completeness basis |
| `crawl_report.json` | same | 1 object | — | entity failures, drift | completeness basis |
| Scopus-guide **tables** snapshot | `docs/qa/gate_d4/common/ictu_web_d4_snapshot_20261029.json` (untracked) | 2 tables: 10 + 59 rows plus header rows | `2ae4301f…` (in-browser `989f6a02…`) | 2026-10-29 01:37:29Z | `ICTU_REPO_SCOPUS_GUIDE` artifact (AMBIGUOUS, UNASSIGNED) |
| Scopus-guide **rows** snapshot | `docs/qa/gate_d3/mission/common/ictu_web_snapshot_20261029.json` (untracked) | 34 rows × 6 cells, no header | `5676e6b0…` (in-browser rows `126b186a…`) | 2026-10-29 00:32:28Z | `ICTU_REPO_SCOPUS_GUIDE` artifact (MULTI_ID) |
| Gate D.1 CSVs `docs/qa/gate_d1r/ictu_*.csv` | tracked | 34 / 10 / 59 rows | — | older transcription | **not used** (superseded by the snapshots; still a data-policy item, §6) |

Lineage chain, stored in each artifact's `capture.upstream`:
1. Upstream file bytes (SHA-256 above).
2. The adapter (`ictu-source-adapters/1`) and its projection version.
3. Canonical artifact bytes (`artifact_bytes`, hashed by `parse_artifact_bytes`).
4. `content_hash`, `capture_hash`, then records and claims.

`capture.upstream` holds the upstream hash, the harvester and parser versions, the in-browser hashes,
the capture notes and the retrieval window. For profiles, `capture.observations[]` keeps the
per-profile provenance in source order: snapshot path, content SHA, HTTP status and `retrieved_at`.

## 2. `lecturers.json`: actual fields and their mapping

Top level: a JSON **list** of 410 objects, all with the same 26 keys.

| Field | Present / shape | Class | In artifact as |
|---|---|---|---|
| `source_id` | 410, URL on the repository host, unique; equals `profile_url` and `provenance.source_url` in 410/410 | CONTENT | `source_id` → STRONG key `PROFILE_SOURCE_ID_V1` |
| `full_name` | 410 text; equals raw label "Họ và tên" in 410/410 | CONTENT | `full_name` (lookup signal only, never a key) |
| `institutional_email` | 410 e-mails, unique after casefold; equals raw label "Email" in 410/410 | CONTENT, **renamed** | `email` → `EMAIL_DECLARED` claim |
| `orcid` | 372 bare iDs, 38 null | CONTENT | `orcid` → `ORCID_DECLARED` claim |
| `profile_url`, `source_display_name`, `orcid_url`, `google_scholar_url`, `academic_degree`, `academic_rank`, `position`, `faculty`, `department`, `specialisation`, `is_active`, `public_publication_links` (0–96 links; 304 profiles have none), `counts` | as found | CONTENT | verbatim |
| `source_fields` (raw page labels) | 2–9 labels per profile | CONTENT, **allowlisted** | verbatim for "Họ và tên", "Email", "ORCID", "Học vị", "Học hàm", "Google Scholar"; all other labels dropped and counted |
| `provenance`, `discovery_source`, `observed_labels`, `preserved_labels`, `lost_labels` | 410 | CAPTURE | `capture.observations[]` (never in the content hash) |
| `normalized`, `source` | 410; derived copies of top-level fields | DERIVED | dropped (the parser normalizes on its own) |
| `extra_fields` (birth date 392, gender 383, phone 330) | 410 | EXCLUDED (personal) | dropped and counted in `capture.excluded` |

Facts that shaped the mapping:
- **The raw ORCID label is not an iD.** Every raw "ORCID" label is `<iD> ↗`, ending in a link icon.
  P1 would mark all 372 raw values invalid. The adapter therefore uses the harvester's extracted
  `orcid` and keeps the raw label verbatim. It also checks that each extracted ORCID, e-mail and name
  is traceable to the raw label text; on the real file there are 0 mismatches. Any mismatch is listed
  in `capture.checks` by position.
- **The file holds unrelated personal data.** Birth date, gender and phone sit in `extra_fields` and in
  `source_fields`. They are not needed for identity resolution and are never copied (decision O-7).
- **Collisions in the real data:** 10 ORCID values are each declared by 2 profiles (20 profiles). All
  20 profiles and claims are kept and reported by `orcid_collision_groups`. There are 0 duplicate
  e-mails and 0 duplicate `source_id` values.
- **Unknown fields fail closed.** An unclassified top-level field raises
  `AdapterError(UNMAPPED_PROFILE_FIELD)`, so a new personal field is neither silently copied nor
  silently dropped.
- **Capture time.** `captured_at` is `harvest_completed_at`. The observed window
  (`retrieved_at_min/max`) is kept, because per-profile retrieval predates the run start (the harvester
  reused cached snapshots).

Completeness is derived, not asserted. `COMPLETE` requires all of the following:
- a crawl report is present;
- `source_card_count` and `lecturer_count` both equal the number of profiles in the file;
- `source_drift_detected` is `false`;
- no lecturer or profile entity failed.

Real harvest: 410 = 410 = 410, no drift, and the only failure is one `master_thesis` entity, so it is
**COMPLETE**. `declared_counts.PROFILES` is the listing card count (410).

## 3. Scopus-guide page: actual snapshots and mapping

The page was captured **twice**, about one hour apart, by two different in-browser extractions. The
adapter keeps them as **two artifacts**. Merging them would mix two observation times into one
content hash.

**Tables snapshot (Gate D.4):** AMBIGUOUS and UNASSIGNED
- The table kind comes from the published section heading. "nhập nhằng" means AMBIGUOUS and
  "chưa xác định" means UNASSIGNED; exactly one of these must match.
- The header row `Tên trên Scopus | Scopus ID | Số bài` maps to `SCOPUS_NAME | SCOPUS_ID |
  DECLARED_PUB_COUNT`. Unknown headers become `OTHER`, and a header without a Scopus ID column is an
  error. Data rows are copied verbatim.
- `page_summary.text` is kept as captured. It is the capture tool's transcription, which includes the
  note "preceded by a total '…: 35'", so it is not purely verbatim page text.
- `declared_counts` = `{AMBIGUOUS_IDS: 10, UNASSIGNED_IDS: 59}`, transcribed from that text. The
  page's "35 multi-ID lecturers" is **not** a structured declared count here: its table is not in this
  capture, and P1's `declared_vs_actual` would report 35 against 0. The adapter rejects a declared
  count for an absent table (`DECLARED_COUNT_FOR_ABSENT_TABLE`).
- Completeness: **COMPLETE**. The DOM extraction took whole tables with their header rows.

**Rows snapshot (Gate D.3):** MULTI_ID
- The 6-cell rows map to the fixed layout `NAME, EMAIL, DECLARED_ID_COUNT, DECLARED_PUB_COUNT,
  PRIMARY_SCOPUS_ID, SCOPUS_ID_LIST`, the layout Gate D.1 transcribed.
- The published headers and table heading were not captured, so they are empty strings and
  `capture.upstream.header_captured = false`. The snapshot's own `multi_id_rows` (34) must equal its
  row count.
- Completeness: **PARTIAL**, recommended (O-8). The extraction filtered rows ("6 cells and an
  @ictu.edu.vn e-mail"). Arithmetic across the two captures does fit (106 rows = 1 + 34 + 11 + 60), but
  it is cross-capture evidence. PARTIAL only prevents withdrawal inference; nothing else changes.

**Three ID categories stay distinct:**
- 83 `SCOPUS_ID_OWNED` claims from 34 rows, subject = row e-mail (MEDIUM);
- 10 `SCOPUS_ID_AMBIGUOUS` and 59 `SCOPUS_ID_UNASSIGNED` claims, no subject;
- 0 IDs shared between the owned and the unowned sets.

The two guide artifacts have different `scope_key`s, so they are never compared for withdrawal
(`SCOPE_DIFFERS`).

## 4. Results of the real run (aggregates)

| Artifact | Records | Status | Keys | Claims | Notes |
|---|---|---|---|---|---|
| PROFILES | 410 (304 without publications) | 410 VALID | 410 `PROFILE_SOURCE_ID_V1`/STRONG | 410 EMAIL, 372 ORCID | 10 ORCID collision groups (20 profiles); declared 410 = actual 410; COMPLETE |
| GUIDE tables | 69 (10 + 59) | 69 VALID | 69 `SCOPUS_ID_V1`/STRONG | 10 AMBIGUOUS, 59 UNASSIGNED | declared counts consistent; COMPLETE |
| GUIDE multi-ID | 34 | 34 VALID | 34 `EMAIL_V1`/MEDIUM | 83 OWNED, 34 EMAIL | PARTIAL; 0 overlap with unowned IDs |

- All three artifacts validate against the JSON Schema.
- Re-encoding gives identical bytes.
- Weak (content) keys: **0**.
- Every multi-ID row e-mail (34/34) also occurs among the 410 profile e-mails. This is a P3 input,
  not a link.

## 5. "410 profiles" is not "410 database records"

- A capture of 410 profiles creates 410 *source records* under one content version.
- A later identical capture creates **no** new records (REUSED).
- None of these records is a `lecturers` row or an identity. P3 resolves them against lecturers as
  evidence, under review.
- The number of lecturers in the application database was not read; P2-A has no database access.

## 6. Known limitations

1. `source_id` paths contain a slug derived from the lecturer's name. A STRONG key assumes the
   repository keeps profile URLs stable. If a renamed profile gets a new URL, it shows as
   withdrawn + new, never as a silent merge.
2. The multi-ID published headers were not captured. A future single full-page capture should
   include headers and all three tables.
3. The tracked Gate D.1 CSVs (`docs/qa/gate_d1r/ictu_*.csv`) contain names and e-mails. This is still
   an open data-policy item from E3-P1, outside the P2-A scope.
4. The Gate D.3/D.4 snapshot files that hold names and e-mails are untracked local files. They must
   stay out of Git.
