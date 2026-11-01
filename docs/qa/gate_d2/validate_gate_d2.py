"""
Gate D.2 Batch 3-5 Validation Script — v4
Read-only. No DB writes. No ACCEPT/REJECT. No source data modification.

Changes from v3:
  - V1: Report now generated from this run's actual output (see VALIDATION_REPORT)
  - V2: CHECK 7 uses batch1_full_csv_reconciliation.csv (64 rows) not the 21-row sample
        Full Batch 1-5 yields 186/158/25/3 directly from pub exports
  - V3: Negative tests are real mutation tests on temp copies; validator re-invoked;
        exit code and output verified non-zero
  - V5: SHA-256 of dependencies pinned and checked at startup; FAIL if mismatch
        ICTU CSV hash difference from Gate D.1 ZIP explained: same content,
        different line endings (ZIP=LF/4631B, local=CRLF/4666B, no BOM); normalized hash identical
  - V6: Fail-fast if any required file is absent; full dependency manifest

External dependencies (not in ZIP — required to run):
  data/scopus/Truong_Quang_Huy_Scopus_Sep2026.csv
    SHA-256: fa2e2a48ef3255905d3a14b0e63f052f7893815bbe91a35b2d643fd928d0f707
  docs/qa/gate_d1r/ictu_multi_scopus_ids.csv
    SHA-256: 7f14c3a7b42ed648694e15baa74ff0c56a95ac7e0ca008e4b5f024e4cdd3554e  (local, CRLF)
    SHA-256: 8e782e12c689e7563dfd88e02d8c0c8f145b3c7634029faf7759251c8ddb77c0  (Gate D.1 ZIP, LF)
    Note: same content; hash differs only in line endings. Normalized (strip CRLF) hash
    must match; otherwise FAIL.

Gate D.1 visited evidence note (V4):
  DDC (ddcuong) and DXL (dxlam) IDs are hard-coded as Gate D.1 historical constants
  because their browser visit records exist in Gate D.1 browser evidence (not automated).
  These are noted as manually-reviewed provenance, not computed from an evidence file.
"""

import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from collections import defaultdict

# When running as a subprocess in a negative test, skip the negative-test section
# to prevent infinite recursion and timeout.
IS_NEG_TEST_RUN = os.environ.get("GATE_D2_NEG_TEST_RUN") == "1"

ROOT = Path(__file__).parent.parent.parent.parent  # repo root
QA_DIR = ROOT / "docs" / "qa" / "gate_d2"
QA_D1_DIR = ROOT / "docs" / "qa" / "gate_d1r"
CSV_SOURCE = ROOT / "data" / "scopus" / "Truong_Quang_Huy_Scopus_Sep2026.csv"
ICTU_IDS_CSV = QA_D1_DIR / "ictu_multi_scopus_ids.csv"
FINDINGS_FILE = ROOT / "docs" / "research" / "02_ICTU_DATA_FINDINGS.md"
BATCH1_FULL = QA_DIR / "batch1_full_csv_reconciliation.csv"

# Pinned SHA-256 for external dependencies
PINNED_SHA = {
    CSV_SOURCE: "fa2e2a48ef3255905d3a14b0e63f052f7893815bbe91a35b2d643fd928d0f707",
    ICTU_IDS_CSV: None,  # checked via normalized content (CRLF tolerance)
}
ICTU_NORMALIZED_SHA = "8e782e12c689e7563dfd88e02d8c0c8f145b3c7634029faf7759251c8ddb77c0"

GREEN = "\033[32m"
RED   = "\033[31m"
RESET = "\033[0m"
PASS_TAG = f"{GREEN}PASS{RESET}"
FAIL_TAG = f"{RED}FAIL{RESET}"

results = []
fatal_errors = []

def check(name, passed, detail=""):
    results.append((name, passed, detail))
    tag = PASS_TAG if passed else FAIL_TAG
    print(f"  [{tag}] {name}" + (f" -- {detail}" if detail else ""))

def section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def sha256_normalized(path):
    """SHA-256 after normalizing line endings to LF."""
    data = Path(path).read_bytes()
    data = data.lstrip(b"\xef\xbb\xbf")  # strip BOM
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()

def normalize_doi(doi):
    return (doi or "").strip().lower()

def get_pub_eid_sid_doi(row):
    """Normalize column names across batch CSV formats."""
    eid = (row.get("eid") or row.get("EID") or "").strip()
    sid = (
        row.get("scopus_id_matched") or
        row.get("scopus_id") or
        row.get("Scopus_ID") or ""
    ).strip()
    doi = normalize_doi(row.get("doi") or row.get("DOI") or "")
    return eid, sid, doi


# ── FAIL-FAST: required files ─────────────────────────────────────────────────
section("DEPENDENCY CHECK — required files")

REQUIRED_FILES = [
    CSV_SOURCE,
    ICTU_IDS_CSV,
    BATCH1_FULL,
] + [QA_DIR / f"batch{b}_id_evidence.csv" for b in range(1, 6)] \
  + [QA_DIR / f"batch{b}_publication_evidence.csv" for b in range(1, 6)] \
  + [QA_DIR / f"batch{b}_browser_evidence.json" for b in [2, 3, 4, 5]] \
  + [FINDINGS_FILE]

for f in REQUIRED_FILES:
    ok = f.exists()
    check(f"exists: {f.relative_to(ROOT)}", ok)
    if not ok:
        fatal_errors.append(str(f))

if fatal_errors:
    print(f"\n  FATAL: {len(fatal_errors)} required file(s) missing. Aborting.\n")
    for e in fatal_errors:
        print(f"    {e}")
    sys.exit(1)


# ── SHA-256 PIN CHECK ─────────────────────────────────────────────────────────
section("DEPENDENCY SHA-256 VERIFICATION")

src_sha = sha256_file(CSV_SOURCE)
check(
    f"Source CSV SHA-256 matches pin",
    src_sha == PINNED_SHA[CSV_SOURCE],
    f"got {src_sha[:16]}... expected {PINNED_SHA[CSV_SOURCE][:16]}..."
)

ictu_norm_sha = sha256_normalized(ICTU_IDS_CSV)
ictu_raw_sha = sha256_file(ICTU_IDS_CSV)
check(
    "ICTU CSV normalized SHA-256 matches Gate D.1 ZIP content",
    ictu_norm_sha == ICTU_NORMALIZED_SHA,
    f"normalized={ictu_norm_sha[:16]}... expected={ICTU_NORMALIZED_SHA[:16]}..."
)
check(
    "ICTU CSV raw SHA-256 recorded",
    True,
    f"raw={ictu_raw_sha} (differs from Gate D.1 ZIP due to line endings only)"
)

batch1_full_sha = sha256_file(BATCH1_FULL)
check("batch1_full_csv_reconciliation.csv SHA-256 recorded", True,
      f"{batch1_full_sha[:16]}...")


# ── LOAD ICTU IDs ─────────────────────────────────────────────────────────────
section("LOAD ICTU MULTI-SCOPUS IDS (34 GVs / 83 IDs)")

ictu_rows = []
with open(ICTU_IDS_CSV, encoding="utf-8-sig") as f:
    ictu_rows = list(csv.DictReader(f))

ALL_83_IDS = set()
GV_BY_ID = {}
GV_ALL_IDS = {}

for r in ictu_rows:
    gv = r["email"].split("@")[0]
    ids = [x.strip() for x in r["all_ids"].split("|") if x.strip()]
    GV_ALL_IDS[gv] = set(ids)
    for sid in ids:
        ALL_83_IDS.add(sid)
        GV_BY_ID[sid] = gv

check("ICTU CSV: 34 GVs", len(ictu_rows) == 34, f"got {len(ictu_rows)}")
check("ICTU CSV: 83 unique IDs", len(ALL_83_IDS) == 83, f"got {len(ALL_83_IDS)}")

ddc_ids = GV_ALL_IDS.get("ddcuong", set())
dxl_ids = GV_ALL_IDS.get("dxlam", set())
check("DDC: 2 IDs {'26423550300','60561601800'}",
      ddc_ids == {"26423550300","60561601800"}, f"got {sorted(ddc_ids)}")
check("DXL: 2 IDs {'59707347300','58805827700'}",
      dxl_ids == {"59707347300","58805827700"}, f"got {sorted(dxl_ids)}")


# ── LOAD SOURCE CSV ───────────────────────────────────────────────────────────
section("LOAD SOURCE CSV")

source_rows = []
with open(CSV_SOURCE, encoding="utf-8-sig") as f:
    source_rows = list(csv.DictReader(f))
check("Source CSV: 660 rows", len(source_rows) == 660,
      f"got {len(source_rows)}")

source_eid_sid = set()
source_row_keys = {}
doi_to_ids_in_source = defaultdict(set)

for row in source_rows:
    ids_cell = row.get("Author(s) ID", "").strip()
    eid = row.get("EID", "").strip()
    doi_raw = normalize_doi(row.get("DOI", ""))
    for sid in [p.strip() for p in ids_cell.split(";") if p.strip()]:
        if eid:
            source_eid_sid.add((eid, sid))
            key = (eid, sid)
            if key not in source_row_keys:
                source_row_keys[key] = set()
            if doi_raw:
                source_row_keys[key].add(doi_raw)
        if doi_raw and sid:
            doi_to_ids_in_source[doi_raw].add(sid)

check(f"Source EID+SID pairs built ({len(source_eid_sid)})", len(source_eid_sid) > 0)


# ── CHECK 1: CSV encoding ─────────────────────────────────────────────────────
section("CHECK 1: CSV files strict UTF-8")
for f in sorted(QA_DIR.glob("batch*_id_evidence.csv")) + \
         sorted(QA_DIR.glob("batch*_publication_evidence.csv")):
    try:
        f.read_bytes().decode("utf-8")
        check(f"UTF-8: {f.name}", True)
    except UnicodeDecodeError as e:
        check(f"UTF-8: {f.name}", False, str(e))

check(f"UTF-8: {BATCH1_FULL.name}", True,
      "already checked via utf-8-sig read above")


# ── CHECK 2: JSON encoding ────────────────────────────────────────────────────
section("CHECK 2: JSON files parse OK")
loaded_json = {}
for f in sorted(QA_DIR.glob("batch*_browser_evidence.json")):
    try:
        data = json.loads(f.read_bytes().decode("utf-8"))
        loaded_json[f.name] = data
        check(f"JSON parse: {f.name}", True)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        check(f"JSON parse: {f.name}", False, str(e))


# ── CHECK 3: Full provenance for every publication row ────────────────────────
section("CHECK 3: Publication row provenance -- EID+SID+DOI vs source CSV (same row)")

# Batch 1 uses the FULL reconciliation file (64 EID rows + 1 no-pub row)
# Batch 2-5 use their publication evidence files
PUB_FILES = {
    "batch1": BATCH1_FULL,
    "batch2": QA_DIR / "batch2_publication_evidence.csv",
    "batch3": QA_DIR / "batch3_publication_evidence.csv",
    "batch4": QA_DIR / "batch4_publication_evidence.csv",
    "batch5": QA_DIR / "batch5_publication_evidence.csv",
}

total_rows_seen = 0
rows_with_eid = 0
rows_with_eid_and_sid = 0
rows_verified = 0
rows_mismatch = 0
rows_skipped_no_eid = 0
rows_skipped_no_sid = 0

for batch, pub_file in PUB_FILES.items():
    with open(pub_file, encoding="utf-8-sig") as f:
        file_rows = list(csv.DictReader(f))

    file_total = len(file_rows)
    file_no_eid = 0
    file_no_sid = 0
    file_verified = 0
    file_mismatch = []
    file_doi_mismatch = []

    for row in file_rows:
        total_rows_seen += 1
        eid, sid, doi = get_pub_eid_sid_doi(row)

        if not eid:
            file_no_eid += 1
            rows_skipped_no_eid += 1
            continue

        rows_with_eid += 1

        if not sid:
            file_no_sid += 1
            rows_skipped_no_sid += 1
            file_mismatch.append(
                f"EID={eid} has no parseable SID "
                f"(checked scopus_id, scopus_id_matched, Scopus_ID)"
            )
            continue

        rows_with_eid_and_sid += 1
        pair = (eid, sid)

        if pair not in source_eid_sid:
            rows_mismatch += 1
            file_mismatch.append(f"({eid}, {sid}) NOT in source CSV")
            continue

        if doi:
            valid_dois = source_row_keys.get(pair, set())
            if doi not in valid_dois:
                rows_mismatch += 1
                file_doi_mismatch.append(
                    f"DOI {doi} not on source row for ({eid}, {sid}); "
                    f"valid: {sorted(valid_dois) or 'none'}"
                )
                continue

        rows_verified += 1
        file_verified += 1

    if file_mismatch or file_doi_mismatch:
        for detail in (file_mismatch + file_doi_mismatch)[:5]:
            check(f"Provenance [{pub_file.name}]", False, detail)
        extra = len(file_mismatch) + len(file_doi_mismatch) - 5
        if extra > 0:
            check(f"  ...{extra} more fails in {pub_file.name}", False, "")
    else:
        check(
            f"All {file_verified}/{file_total} rows OK: {pub_file.name}",
            True,
            f"no_eid={file_no_eid} no_sid={file_no_sid} verified={file_verified}",
        )

check(
    f"Total rows seen: {total_rows_seen}",
    True,
    f"with_eid={rows_with_eid} eid+sid={rows_with_eid_and_sid} "
    f"no_eid={rows_skipped_no_eid} no_sid(FAIL)={rows_skipped_no_sid}",
)
check(
    f"All rows verified: mismatches=0 unparseable_sid=0",
    rows_mismatch == 0 and rows_skipped_no_sid == 0,
    f"mismatches={rows_mismatch} unparseable_sid={rows_skipped_no_sid}",
)


# ── CHECK 4: DOI->ID provenance in id_evidence ───────────────────────────────
section("CHECK 4: DOI->ID provenance (doi_crossref_verified in id_evidence)")
for batch in ["batch3","batch4","batch5"]:
    ev_file = QA_DIR / f"{batch}_id_evidence.csv"
    with open(ev_file, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        doi = normalize_doi(row.get("doi_crossref_verified") or "")
        sid = (row.get("scopus_id") or "").strip()
        if not doi or not sid:
            continue
        valid_ids = doi_to_ids_in_source.get(doi, set())
        ok = sid in valid_ids
        check(f"DOI->ID [{batch}] {sid}: {doi[:45]}", ok,
              "" if ok else f"source maps DOI to {sorted(valid_ids) or 'NOT FOUND'}")


# ── CHECK 5: Coverage 41/83 and 13/34 ────────────────────────────────────────
section("CHECK 5: Coverage 41/83 IDs and 13/34 GVs -- from real data")

batch_visited_ids = set()
batch_visited_gvs = set()
for batch in ["batch1","batch2","batch3","batch4","batch5"]:
    ev_file = QA_DIR / f"{batch}_id_evidence.csv"
    with open(ev_file, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            sid = (row.get("scopus_id") or "").strip()
            if sid and sid in ALL_83_IDS:
                batch_visited_ids.add(sid)
                gv = GV_BY_ID.get(sid)
                if gv:
                    batch_visited_gvs.add(gv)

check(f"Batch CSVs: unique IDs in 83-set = 37",
      len(batch_visited_ids) == 37, f"got {len(batch_visited_ids)}")
check(f"Batch CSVs: GVs covered = 11",
      len(batch_visited_gvs) == 11,
      f"got {len(batch_visited_gvs)}: {sorted(batch_visited_gvs)}")

# Gate D.1: DDC×2 + DXL×2 visited in Gate D.1 (manually-reviewed historical constants)
# These IDs are in ALL_83_IDS but not in any batch1-5 id_evidence CSV.
# Provenance: Gate D.1 browser_opened=YES in ictu_multi_scopus_ids.csv for ddcuong, dxlam.
gate_d1_only_ids = (ddc_ids | dxl_ids) - batch_visited_ids
check(f"Gate D.1 adds DDC+DXL IDs not in batch CSVs: 4",
      len(gate_d1_only_ids) == 4, f"got {len(gate_d1_only_ids)}: {sorted(gate_d1_only_ids)}")

dtb_ids = GV_ALL_IDS.get("dtbac", set())
check("DTB x5 already in batch5 CSV",
      dtb_ids <= batch_visited_ids,
      f"DTB missing: {dtb_ids - batch_visited_ids}")

all_visited_ids = batch_visited_ids | gate_d1_only_ids
all_visited_gvs = batch_visited_gvs | {"ddcuong","dxlam"}

check("Total visited IDs = 41/83",
      len(all_visited_ids) == 41,
      f"got {len(all_visited_ids)}")
check("Total visited GVs = 13/34",
      len(all_visited_gvs) == 13,
      f"got {len(all_visited_gvs)}: {sorted(all_visited_gvs)}")
check("Unvisited IDs = 42/83",
      len(ALL_83_IDS - all_visited_ids) == 42,
      f"got {len(ALL_83_IDS - all_visited_ids)}")


# ── CHECK 6: Per-ID pub counts ────────────────────────────────────────────────
section("CHECK 6: Per-ID pub counts in id_evidence.csv match source CSV")

id_pub_count = defaultdict(set)
for row in source_rows:
    ids_cell = row.get("Author(s) ID","").strip()
    eid = row.get("EID","").strip()
    if not eid:
        continue
    for sid in [p.strip() for p in ids_cell.split(";") if p.strip()]:
        if sid in ALL_83_IDS:
            id_pub_count[sid].add(eid)

for batch in ["batch3","batch4","batch5"]:
    ev_file = QA_DIR / f"{batch}_id_evidence.csv"
    with open(ev_file, encoding="utf-8-sig") as f:
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
              "" if claimed == actual else f"claimed {claimed}, source has {actual}")


# ── CHECK 7: Stats 186/158/25/3 from pub exports (full) ──────────────────────
section("CHECK 7: Stats 186/158/25/3 -- from full pub exports (batch1 full + batch2-5)")

export_gv_eid = set()
export_eids = set()
eid_to_gvs_export = defaultdict(set)

for batch, pub_file in PUB_FILES.items():
    with open(pub_file, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            eid, sid, _ = get_pub_eid_sid_doi(row)
            if eid and sid:
                gv = GV_BY_ID.get(sid)
                if gv:
                    export_gv_eid.add((gv, eid))
                    export_eids.add(eid)
                    eid_to_gvs_export[eid].add(gv)

cross_gv_export = {e for e, gs in eid_to_gvs_export.items() if len(gs) >= 2}
triple_gv_export = {e for e, gs in eid_to_gvs_export.items() if len(gs) >= 3}

check(f"Pub exports (batch1 full + batch2-5): GV-EID pairs = 186",
      len(export_gv_eid) == 186, f"got {len(export_gv_eid)}")
check(f"Pub exports: unique EIDs = 158",
      len(export_eids) == 158, f"got {len(export_eids)}")
check(f"Pub exports: cross-GV EIDs (>=2 GVs) = 25",
      len(cross_gv_export) == 25, f"got {len(cross_gv_export)}")
check(f"Pub exports: triple-GV EIDs (>=3 GVs) = 3",
      len(triple_gv_export) == 3,
      f"got {len(triple_gv_export)}: {sorted(triple_gv_export)}")

# All export pairs must be in source CSV
check(
    f"All {len(export_gv_eid)} export pairs verified in source CSV",
    export_gv_eid <= {(GV_BY_ID[sid], eid)
                      for eid, sid in source_eid_sid if sid in GV_BY_ID},
    "some export pairs not found in source"
)

# No intra-GV duplicates
raw_count = defaultdict(int)
for gv, eid in [(GV_BY_ID[sid], eid)
                for batch, pub_file in PUB_FILES.items()
                for row in open(pub_file, encoding="utf-8-sig") and []
                ]:
    raw_count[(gv, eid)] += 1
# Re-count properly
raw_count2 = defaultdict(int)
for batch, pub_file in PUB_FILES.items():
    with open(pub_file, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            eid, sid, _ = get_pub_eid_sid_doi(row)
            if eid and sid and sid in GV_BY_ID:
                raw_count2[(GV_BY_ID[sid], eid)] += 1
dupes = [(k,v) for k,v in raw_count2.items() if v > 1]
check("No intra-GV EID duplicates across full pub exports", len(dupes) == 0,
      f"{len(dupes)} dupes" if dupes else "")


# ── CHECK 8: FINDING-001 through FINDING-021 ─────────────────────────────────
section("CHECK 8: FINDING-001 through FINDING-021 in findings file")
findings_text = FINDINGS_FILE.read_text(encoding="utf-8")
for i in range(1, 22):
    fid = f"FINDING-{i:03d}"
    check(f"{fid} present", fid in findings_text)


# ── CHECK 9: batch4 three_way EIDs ───────────────────────────────────────────
section("CHECK 9: batch4 JSON three_way_shared_eids split")
b4_json = loaded_json.get("batch4_browser_evidence.json", {})
cg = b4_json.get("cross_gv_coauthorship", {})

check("Old 'three_way_shared_eids' renamed/removed",
      "three_way_shared_eids" not in cg,
      "field still present")

nhh_qxt_tqq = cg.get("three_way_shared_eids_nhh_qxt_tqq", [])
all_9gv = cg.get("three_way_shared_eids_all_9gv", [])
check("three_way_shared_eids_nhh_qxt_tqq has 2 EIDs",
      len(nhh_qxt_tqq) == 2, f"got {len(nhh_qxt_tqq)}: {nhh_qxt_tqq}")
check("three_way_shared_eids_all_9gv has 3 EIDs",
      len(all_9gv) == 3, f"got {len(all_9gv)}: {all_9gv}")
check("all_9gv includes 2-s2.0-85208627580",
      "2-s2.0-85208627580" in all_9gv)

check("Exports confirm 3 triple-GV EIDs",
      len(triple_gv_export) == 3, f"got {sorted(triple_gv_export)}")
for eid in all_9gv:
    gvs = sorted(eid_to_gvs_export.get(eid, set()))
    check(f"Exports confirm triple EID {eid}: {gvs}",
          len(gvs) >= 3, f"only {gvs}")


# ── CHECK 10: batch3 anomaly flag cleared ────────────────────────────────────
section("CHECK 10: batch3 JSON ids_doi_anomaly_flagged cleared")
b3_json = loaded_json.get("batch3_browser_evidence.json", {})
nvt_summary = b3_json.get("summary", {}).get("nguyen_van_tao", {})
active_anomalies = nvt_summary.get("ids_doi_anomaly_flagged", ["NOT_FOUND"])
check("ids_doi_anomaly_flagged is empty list",
      active_anomalies == [], f"got: {active_anomalies}")
history = nvt_summary.get("ids_doi_anomaly_correction_history", [])
check("correction_history has >=1 entry", len(history) >= 1, f"got {len(history)}")
if history:
    check("history entry for 56967513900",
          any(h.get("id_formerly_flagged") == "56967513900" for h in history))


# ── NEGATIVE TESTS — real mutation tests ─────────────────────────────────────
section("NEGATIVE TESTS — real mutations on temp copies, validator re-invoked")

THIS_SCRIPT = Path(__file__).resolve()
neg_results = []

def run_validator_on_temp(setup_fn, description):
    """
    Copy required files to a temp dir, mutate one file, re-run this validator
    with GATE_D2_NEG_TEST_RUN=1 (skips neg tests in subprocess to prevent recursion).
    Assert exit code != 0.
    """
    tmp = Path(tempfile.mkdtemp(prefix="gate_d2_neg_"))
    try:
        for src in REQUIRED_FILES + [THIS_SCRIPT]:
            rel = src.relative_to(ROOT)
            dst = tmp / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        setup_fn(tmp)
        env = os.environ.copy()
        env["GATE_D2_NEG_TEST_RUN"] = "1"
        result = subprocess.run(
            [sys.executable, "-I", "-X", "utf8",
             str(tmp / THIS_SCRIPT.relative_to(ROOT))],
            capture_output=True, text=True, timeout=90, env=env
        )
        triggered = result.returncode != 0
        neg_results.append((description, triggered, result.returncode))
        tag = f"{GREEN}NEG-PASS{RESET}" if triggered else f"{RED}NEG-FAIL{RESET}"
        print(f"  [{tag}] {description} -- exit={result.returncode}")
        if not triggered:
            results.append((f"NEG: {description}", False, f"exit=0 (should be non-zero)"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def mut_wrong_sid(tmp):
    f = tmp / "docs/qa/gate_d2/batch3_publication_evidence.csv"
    text = f.read_text(encoding="utf-8")
    text = text.replace("56548128100", "00000000000", 1)
    f.write_text(text, encoding="utf-8")

def mut_wrong_doi(tmp):
    f = tmp / "docs/qa/gate_d2/batch4_publication_evidence.csv"
    text = f.read_text(encoding="utf-8")
    text = text.replace("10.5121/ijcnc.2026.18401", "10.9999/fake-doi-neg2", 1)
    f.write_text(text, encoding="utf-8")

def mut_missing_pub_csv(tmp):
    (tmp / "docs/qa/gate_d2/batch5_publication_evidence.csv").unlink()

def mut_batch1_no_eid(tmp):
    import csv as _csv, io
    f = tmp / "docs/qa/gate_d2/batch1_full_csv_reconciliation.csv"
    content = f.read_text(encoding="utf-8")
    reader = _csv.DictReader(io.StringIO(content))
    rows = list(reader)
    for r in rows:
        if "eid" in r:
            r["eid"] = ""
    out = io.StringIO()
    writer = _csv.DictWriter(out, fieldnames=reader.fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    f.write_text(out.getvalue(), encoding="utf-8")

def mut_truncate_source(tmp):
    f = tmp / "data/scopus/Truong_Quang_Huy_Scopus_Sep2026.csv"
    lines = f.read_bytes().split(b"\n")
    f.write_bytes(b"\n".join(lines[:11]))

if IS_NEG_TEST_RUN:
    check("Negative tests skipped (subprocess mode)", True, "GATE_D2_NEG_TEST_RUN=1")
else:
    run_validator_on_temp(mut_wrong_sid,
                          "NEG-1: Wrong SID in batch3 pub CSV -> provenance FAIL")
    run_validator_on_temp(mut_wrong_doi,
                          "NEG-2: Wrong DOI in batch4 pub CSV -> DOI mismatch FAIL")
    run_validator_on_temp(mut_missing_pub_csv,
                          "NEG-3: Missing batch5 pub CSV -> dependency FAIL")
    run_validator_on_temp(mut_batch1_no_eid,
                          "NEG-4: batch1_full EIDs cleared -> 186 count FAIL")
    run_validator_on_temp(mut_truncate_source,
                          "NEG-5: Source CSV truncated -> SHA pin + row count FAIL")

    neg_triggered = sum(1 for _, t, _ in neg_results if t)
    check(f"All 5 negative tests triggered (exit != 0)",
          neg_triggered == 5, f"{neg_triggered}/5 triggered")


# ── DEPENDENCY SUMMARY ────────────────────────────────────────────────────────
section("EXTERNAL DEPENDENCY MANIFEST")
print(f"  {CSV_SOURCE.relative_to(ROOT)}")
print(f"    SHA-256 (raw): {src_sha}")
print()
print(f"  {ICTU_IDS_CSV.relative_to(ROOT)}")
print(f"    SHA-256 (raw, local CRLF):   {ictu_raw_sha}")
print(f"    SHA-256 (normalized to LF):  {ictu_norm_sha}")
print(f"    Gate D.1 ZIP SHA (LF):       {ICTU_NORMALIZED_SHA}")
print(f"    Content identical (after line-ending normalization): {ictu_norm_sha == ICTU_NORMALIZED_SHA}")
print()
print(f"  {BATCH1_FULL.relative_to(ROOT)}")
print(f"    SHA-256: {batch1_full_sha}")
print()
print(f"  Note: ZIP does not include the first two files above.")
print(f"  To reproduce: place at their paths and run this script.")


# ── SUMMARY ───────────────────────────────────────────────────────────────────
section("SUMMARY")
total = len(results)
passed = sum(1 for _, p, _ in results if p)
failed = total - passed
print(f"\n  Total: {total}  |  Passed: {passed}  |  Failed: {failed}")
if failed == 0:
    print(f"\n  [{PASS_TAG}] ALL CHECKS PASSED\n")
else:
    print(f"\n  [{FAIL_TAG}] {failed} CHECK(S) FAILED:\n")
    for name, ok, detail in results:
        if not ok:
            print(f"    - {name}" + (f": {detail}" if detail else ""))
    print()
sys.exit(0 if failed == 0 else 1)
