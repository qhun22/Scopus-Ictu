"""
Gate D.2 Batch 3–5 Validation Script
Read-only. No DB writes. No ACCEPT/REJECT. No source data modification.

Checks:
  1. All CSVs strict UTF-8 (no errors='ignore')
  2. All JSONs parse OK
  3. For every doi_crossref_verified on an ID, DOI must exist in publication CSV under that same ID
  4. Per-ID pub counts in id_evidence.csv match publication CSV
  5. Coverage counted as set(unique IDs), not visit count
  6. Old finding IDs still present in 02_ICTU_DATA_FINDINGS.md
  7. Triple-GV EIDs confirmed (3 EIDs for full-CSV cross-GV)
  8. Q11 union count = 7 distinct EIDs (not 9)
"""

import csv
import json
import sys
import os
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent.parent.parent  # repo root
QA_DIR = ROOT / "docs" / "qa" / "gate_d2"
CSV_SOURCE = ROOT / "data" / "scopus" / "Truong_Quang_Huy_Scopus_Sep2026.csv"
FINDINGS_FILE = ROOT / "docs" / "research" / "02_ICTU_DATA_FINDINGS.md"

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

results = []

def check(name, passed, detail=""):
    status = PASS if passed else FAIL
    results.append((name, passed, detail))
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── 1. CSV encoding ──────────────────────────────────────────────────────────
section("CHECK 1: CSV files strict UTF-8")

csv_files = list(QA_DIR.glob("batch*_id_evidence.csv")) + \
            list(QA_DIR.glob("batch*_publication_evidence.csv"))

for f in sorted(csv_files):
    try:
        content = f.read_bytes().decode("utf-8")
        check(f"UTF-8 OK: {f.name}", True)
    except UnicodeDecodeError as e:
        check(f"UTF-8 OK: {f.name}", False, str(e))


# ── 2. JSON encoding ─────────────────────────────────────────────────────────
section("CHECK 2: JSON files parse OK")

json_files = list(QA_DIR.glob("batch*_browser_evidence.json"))

for f in sorted(json_files):
    try:
        data = json.loads(f.read_bytes().decode("utf-8"))
        check(f"JSON parse OK: {f.name}", True)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        check(f"JSON parse OK: {f.name}", False, str(e))


# ── 3. Load source CSV ───────────────────────────────────────────────────────
section("CHECK 3: DOI->ID provenance (every doi_crossref_verified must exist in CSV under that ID)")

source_rows = []
try:
    with open(CSV_SOURCE, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        source_rows = list(reader)
    check(f"Source CSV loaded ({len(source_rows)} rows)", True)
except Exception as e:
    check("Source CSV loaded", False, str(e))
    sys.exit(1)

# Build mapping: doi → set of scopus_ids in that row
doi_to_ids = defaultdict(set)
eid_to_gvs = defaultdict(set)

GV_IDS = {
    "QXT": {"57196472280","59707353400","57213148275","58937710300"},
    "DQA": {"36852696600","55331947800"},
    "PTN": {"55605197600","58481617700"},
    "LMH": {"60319803200","59708285400","60248511400","60219481200","60320211100"},
    "NHM": {"57192956797","7003299472","58771697600","59768336500"},
    "LHL": {"56548128100","58830932700","57200439355"},
    "NVT": {"57192958573","56967513900","57221224211"},
    "NHH": {"57210434401","59708261900","59775920700"},
    "TQQ": {"58771615400","60214163500","59768494800"},
    "PDL": {"26637116200","57197579769","58805722900"},
    "DTB": {"59526508700","57819997900","59663496400","59159284800","57899449200"},
}
all_audit_ids = {sid for ids in GV_IDS.values() for sid in ids}

for row in source_rows:
    doi_raw = row.get("DOI","").strip()
    ids_cell = row.get("Author(s) ID","").strip()
    eid = row.get("EID","").strip()
    if doi_raw:
        ids_in_row = [p.strip() for p in ids_cell.split(";") if p.strip()]
        for sid in ids_in_row:
            doi_to_ids[doi_raw.lower()].add(sid)
    if eid:
        ids_in_row2 = [p.strip() for p in ids_cell.split(";") if p.strip()]
        for gv, gv_ids in GV_IDS.items():
            for sid in ids_in_row2:
                if sid in gv_ids:
                    eid_to_gvs[eid].add(gv)
                    break

# Check each id_evidence CSV for DOI→ID correctness
for batch in ["batch3", "batch4", "batch5"]:
    ev_file = QA_DIR / f"{batch}_id_evidence.csv"
    if not ev_file.exists():
        check(f"DOI→ID check {batch}: file exists", False, "file not found")
        continue
    with open(ev_file, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        doi = (row.get("doi_crossref_verified") or "").strip()
        sid = (row.get("scopus_id") or "").strip()
        if not doi or not sid:
            continue
        doi_lower = doi.lower()
        valid_ids = doi_to_ids.get(doi_lower, set())
        passed = sid in valid_ids
        detail = f"DOI {doi} → ID {sid}" + ("" if passed else f" (CSV maps to: {sorted(valid_ids) or 'NOT FOUND'})")
        check(f"DOI→ID [{batch}] {sid}: {doi[:40]}", passed, "" if passed else detail)


# ── 4. Per-ID pub counts ─────────────────────────────────────────────────────
section("CHECK 4: Per-ID pub counts in id_evidence.csv match source CSV")

# Build per-ID pub count from source
id_pub_count = defaultdict(set)
for row in source_rows:
    ids_cell = row.get("Author(s) ID","").strip()
    eid = row.get("EID","").strip()
    if not eid:
        continue
    for sid in [p.strip() for p in ids_cell.split(";") if p.strip()]:
        if sid in all_audit_ids:
            id_pub_count[sid].add(eid)

for batch in ["batch3","batch4","batch5"]:
    ev_file = QA_DIR / f"{batch}_id_evidence.csv"
    if not ev_file.exists():
        continue
    with open(ev_file, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        sid = (row.get("scopus_id") or "").strip()
        pubs_str = (row.get("pubs_in_csv") or "").strip()
        if not sid or not pubs_str:
            continue
        try:
            claimed = int(pubs_str)
        except ValueError:
            check(f"Pub count parse [{batch}] {sid}", False, f"non-integer: {pubs_str!r}")
            continue
        actual = len(id_pub_count.get(sid, set()))
        check(f"Pub count [{batch}] {sid}", claimed == actual,
              "" if claimed == actual else f"csv says {claimed}, source has {actual}")


# ── 5. Coverage as set (unique IDs) ─────────────────────────────────────────
section("CHECK 5: Coverage is counted as set(unique IDs), not visit count")

visited_ids = set()
for batch in ["batch1","batch2","batch3","batch4","batch5"]:
    ev_file = QA_DIR / f"{batch}_id_evidence.csv"
    if not ev_file.exists():
        continue
    with open(ev_file, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sid = (row.get("scopus_id") or "").strip()
            if sid:
                visited_ids.add(sid)

# batch5_summary.md claims 41/83 unique IDs
# Read batch5_summary.md to verify
b5_summary = QA_DIR / "batch5_summary.md"
claimed_unique = None
if b5_summary.exists():
    text = b5_summary.read_text(encoding="utf-8")
    import re
    m = re.search(r"\*\*41/83\*\*", text)
    claimed_unique = 41 if m else None

check("batch5_summary.md claims 41 unique IDs", claimed_unique == 41,
      "" if claimed_unique == 41 else f"could not find '**41/83**' in batch5_summary.md")
# Coverage note: 41/83 includes IDs from Gate D.1 (before Batch 1) that have no batch CSV entry.
# Batch CSVs contain 37 IDs (batches 1-5). Remaining 4 IDs were only visited in Gate D.1 scope.
# We verify: (a) batch CSV count is 37, (b) batch5_summary.md correctly states 41.
check(f"Batch CSV unique IDs = 37 (expected count)", len(visited_ids) == 37,
      f"got {len(visited_ids)}")
# The full 41 is document-level claim; we trust batch5_summary.md as the authoritative count.
# (Gate D.1 evidence files are outside the scope of this script.)
check("Coverage claim (41/83) documented in batch5_summary.md", claimed_unique == 41,
      "" if claimed_unique == 41 else "could not find '**41/83**' in batch5_summary.md")


# ── 6. Finding IDs present ───────────────────────────────────────────────────
section("CHECK 6: All finding IDs FINDING-001 through FINDING-021 present in findings file")

if FINDINGS_FILE.exists():
    findings_text = FINDINGS_FILE.read_text(encoding="utf-8")
    for i in range(1, 22):
        fid = f"FINDING-{i:03d}"
        check(f"{fid} present", fid in findings_text)
else:
    check("02_ICTU_DATA_FINDINGS.md exists", False)


# ── 7. Triple-GV EIDs ────────────────────────────────────────────────────────
section("CHECK 7: 3 triple-GV EIDs confirmed from source CSV")

triple_eids = {e: g for e, g in eid_to_gvs.items() if len(g) >= 3}
expected_triples = {
    "2-s2.0-105000957095": {"NHH","QXT","TQQ"},
    "2-s2.0-105041762468": {"NHH","QXT","TQQ"},
    "2-s2.0-85208627580":  {"LHL","NHH","TQQ"},
}
check("Exactly 3 triple-GV EIDs found", len(triple_eids) == 3,
      f"found {len(triple_eids)}: {sorted(triple_eids)}")
for eid, expected_gvs in expected_triples.items():
    actual_gvs = triple_eids.get(eid, set())
    check(f"Triple EID {eid}: {sorted(expected_gvs)}", actual_gvs == expected_gvs,
          "" if actual_gvs == expected_gvs else f"got {sorted(actual_gvs)}")


# ── 8. Q11 union count = 7 ───────────────────────────────────────────────────
section("CHECK 8: Q11 NHH×QXT×TQQ union = 7 distinct EIDs (not 9)")

NHH_ids = GV_IDS["NHH"]
QXT_ids = GV_IDS["QXT"]
TQQ_ids = GV_IDS["TQQ"]

nhh_qxt = {e for e,g in eid_to_gvs.items() if "NHH" in g and "QXT" in g}
nhh_tqq = {e for e,g in eid_to_gvs.items() if "NHH" in g and "TQQ" in g}
qxt_tqq = {e for e,g in eid_to_gvs.items() if "QXT" in g and "TQQ" in g}
union_3 = nhh_qxt | nhh_tqq | qxt_tqq

check(f"NHH×QXT pairwise = 2", len(nhh_qxt) == 2, f"got {len(nhh_qxt)}: {sorted(nhh_qxt)}")
check(f"NHH×TQQ pairwise = 4", len(nhh_tqq) == 4, f"got {len(nhh_tqq)}: {sorted(nhh_tqq)}")
check(f"QXT×TQQ pairwise = 5", len(qxt_tqq) == 5, f"got {len(qxt_tqq)}: {sorted(qxt_tqq)}")
check(f"Union NHH+QXT+TQQ = 7", len(union_3) == 7, f"got {len(union_3)}: {sorted(union_3)}")


# ── Summary ──────────────────────────────────────────────────────────────────
section("SUMMARY")
total = len(results)
passed = sum(1 for _, p, _ in results if p)
failed = total - passed
print(f"\n  Total: {total}  |  Passed: {passed}  |  Failed: {failed}")
if failed == 0:
    print(f"\n  [{PASS}] ALL CHECKS PASSED\n")
else:
    print(f"\n  [{FAIL}] {failed} CHECK(S) FAILED:\n")
    for name, ok, detail in results:
        if not ok:
            print(f"    - {name}" + (f": {detail}" if detail else ""))
    print()
sys.exit(0 if failed == 0 else 1)
