# Gate D.2 Batch 1–5 — Validation Report (Validator v4, handover check)

**Date:** 2026-10-28
**Validator:** `validate_gate_d2.py` v4 (label fixes only since first v4 run; no logic change)
**Result:** 125/125 PASS, exit 0 — run log `validate_v4_run_log.txt`
**Negative tests:** 5/5 NEG-PASS, verified for cause by `neg_test_evidence.py` → `neg_test_evidence_20261028.json`

> This report does not state the SHA-256 of the ZIP that contains it. Per-file content hashes are in `MANIFEST_v4.txt` inside the ZIP. The ZIP's own hash is published outside the package in `gate_d2_batch3to5_validator_v4_20261028.zip.sha256`.

---

## 1. Reproduce

```bash
python -I -X utf8 docs/qa/gate_d2/validate_gate_d2.py        # expect 125/125, exit 0
python -I -X utf8 docs/qa/gate_d2/neg_test_evidence.py       # expect 5/5 NEG-PASS, exit 0
```

## 2. External dependencies (not in ZIP)

| File | SHA-256 (raw) | Notes |
|---|---|---|
| `data/scopus/Truong_Quang_Huy_Scopus_Sep2026.csv` | `fa2e2a48ef3255905d3a14b0e63f052f7893815bbe91a35b2d643fd928d0f707` | Pinned; validator FAILs on mismatch |
| `docs/qa/gate_d1r/ictu_multi_scopus_ids.csv` (local) | `7f14c3a7b42ed648694e15baa74ff0c56a95ac7e0ca008e4b5f024e4cdd3554e` | CRLF, 4,666 bytes, no BOM |
| same file inside `gate_d1_final_20261027.zip` and `gate_d1r_artifacts_20261027.zip` | `8e782e12c689e7563dfd88e02d8c0c8f145b3c7634029faf7759251c8ddb77c0` | LF, 4,631 bytes, no BOM |
| `docs/research/02_ICTU_DATA_FINDINGS.md` | see MANIFEST | Read for FINDING-001…021 |

## 3. ICTU CSV — local vs Gate D.1 (field-level comparison)

Correction to the earlier v4 report: it said local=LF and ZIP=CRLF. **The reverse is true**: local=CRLF, ZIP=LF.

| Property | Local | Gate D.1 ZIP (both ZIPs) |
|---|---|---|
| Bytes | 4,666 | 4,631 (difference = 35 CR bytes) |
| BOM | none | none |
| Line endings | 35 × CRLF | 35 × LF |
| Trailing newline | yes | yes |
| Header (10 columns) | `row,name,email,id_count_ictu_claimed,pub_count_ictu,primary_id,all_ids,source,browser_opened,notes` | identical |
| Data rows | 34 | 34 |
| Cells differing after CSV parse | 0 | 0 |
| SHA-256 after CRLF→LF normalization | `8e782e12…` | `8e782e12…` |

So the content is identical at the field level, with no BOM difference. The validator's "Content identical" line is now computed (it was previously hard-coded `True`).

## 4. Negative tests — evidence of cause

Method (`neg_test_evidence.py`): for each test, copy all 19 required files to a fresh temp dir → run baseline → hash the tree → apply the validator's own mutation function → hash again → run the validator → collect `[FAIL]`/`FATAL`/traceback lines → match them against the expected failure. Repo originals are hashed before and after the whole run.

| Test | Mutation | Baseline | Files changed | Mutated exit | Totals (all / pass / fail) | Expected failure observed |
|---|---|---|---|---|---|---|
| NEG-1 | SID `56548128100`→`00000000000` (1st occurrence) in batch3 pub CSV | exit 0, 125/125 | batch3_publication_evidence.csv only | 1 | 125 / 121 / 4 | `Provenance [batch3…] (2-s2.0-105038090067, 00000000000) NOT in source CSV` |
| NEG-2 | DOI `10.5121/ijcnc.2026.18401`→fake in batch4 pub CSV | exit 0, 125/125 | batch4_publication_evidence.csv only | 1 | 125 / 123 / 2 | `Provenance [batch4…] DOI 10.9999/fake-doi-neg2 not on source row for (2-s2.0-105046197896, 59775920700)` |
| NEG-3 | delete batch5 pub CSV | exit 0, 125/125 | batch5_publication_evidence.csv only | 1 | fail-fast (no totals) | `exists: …batch5_publication_evidence.csv` + `FATAL: 1 required file(s) missing` |
| NEG-4 | clear every `eid` in batch1_full | exit 0, 125/125 | batch1_full_csv_reconciliation.csv only | 1 | 125 / 118 / 7 | `GV-EID pairs = 186 -- got 122`, `unique EIDs = 158 -- got 106`, cross-GV 25→15, triple-GV 3→1 |
| NEG-5 | truncate source CSV to 11 lines | exit 0, 125/125 | source CSV only | 1 | 150 / 87 / 63 | `Source CSV SHA-256 matches pin -- got b7c475ab… expected fa2e2a48…`, `Source CSV: 660 rows -- got 10`, 181 provenance mismatches |

- No test exited because of a traceback or a path error; every failure is a named assertion.
- Side effects are expected and match the mutation: in NEG-1 the altered SID no longer maps to a GV, so pairs go 186→185 and cross-GV goes 25→24.
- **Repo originals unchanged:** all 19 files hash the same before and after (`originals_unchanged: true` in the JSON).

## 5. Fixes since the first v4 run (labels only)

1. Swapped the docstring and manifest line-ending labels (local=CRLF, ZIP=LF).
2. `Content identical` is now computed from the hash comparison instead of hard-coded.
3. Row-count check label: it was `Source CSV: {actual} rows`, which printed "10 rows -- got 10" under mutation; it is now fixed text `Source CSV: 660 rows`.

None of these changes the pass/fail logic. After the edits: 125/125 PASS again.

## 6. Known limitation (unchanged)

The Gate D.1 visits for DDC/DXL (4 IDs) are hard-coded historical constants, cross-checked against `browser_opened=YES` in the ICTU CSV rather than read from a Gate D.1 browser-evidence file.

## 7. Constraints observed

No DB writes, no ACCEPT/REJECT/REVOKE, no Scopus ID merges, no changes to ICTU source data, no backend/frontend edits, no pytest or migration, no commit or push.
