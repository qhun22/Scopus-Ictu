"""Evidence harness for validate_gate_d2.py v4 negative tests.

For each mutation: baseline PASS on an identical temp copy, mutation changes
bytes of exactly one file, subprocess FAIL lines captured, originals unchanged.
Read-only with respect to the repo.
"""
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
VALIDATOR = HERE / "validate_gate_d2.py"
ROOT = HERE.parent.parent.parent

ANSI = re.compile(r"\x1b\[[0-9;]*m")

# Expected failing check, by substring of the check name / fatal message.
EXPECTED = {
    "NEG-1": ["CHECK 3", "provenance", "batch3"],
    "NEG-2": ["DOI"],
    "NEG-3": ["exists: docs", "batch5_publication_evidence.csv"],
    "NEG-4": ["186", "pairs"],
    "NEG-5": ["SHA-256", "source"],
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_validator_defs():
    """Pull REQUIRED_FILES + mutation fns without executing the validator body."""
    src = VALIDATOR.read_text(encoding="utf-8")
    start = src.index("def mut_wrong_sid")
    end = src.index("if IS_NEG_TEST_RUN:")
    ns = {"Path": Path}
    exec(src[start:end], ns)
    return ns


def required_files():
    rels = [
        "data/scopus/Truong_Quang_Huy_Scopus_Sep2026.csv",
        "docs/qa/gate_d1r/ictu_multi_scopus_ids.csv",
        "docs/qa/gate_d2/batch1_full_csv_reconciliation.csv",
        "docs/research/02_ICTU_DATA_FINDINGS.md",
    ]
    rels += [f"docs/qa/gate_d2/batch{b}_id_evidence.csv" for b in range(1, 6)]
    rels += [f"docs/qa/gate_d2/batch{b}_publication_evidence.csv" for b in range(1, 6)]
    rels += [f"docs/qa/gate_d2/batch{b}_browser_evidence.json" for b in (2, 3, 4, 5)]
    rels += ["docs/qa/gate_d2/validate_gate_d2.py"]
    return [ROOT / r for r in rels]


def make_copy():
    tmp = Path(tempfile.mkdtemp(prefix="gate_d2_evi_"))
    for f in required_files():
        dst = tmp / f.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
    return tmp


def run(tmp):
    env = os.environ.copy()
    env["GATE_D2_NEG_TEST_RUN"] = "1"
    r = subprocess.run(
        [sys.executable, "-I", "-X", "utf8",
         str(tmp / "docs/qa/gate_d2/validate_gate_d2.py")],
        capture_output=True, text=True, encoding="utf-8", timeout=120, env=env)
    out = ANSI.sub("", r.stdout + r.stderr)
    fails = [l.strip() for l in out.splitlines()
             if "[FAIL]" in l or "FATAL" in l
             or "Traceback" in l or "Error:" in l]
    total = re.search(r"Total: (\d+)\s+\|\s+Passed: (\d+)\s+\|\s+Failed: (\d+)", out)
    return r.returncode, fails, total.groups() if total else None, out


def tree_hashes(tmp):
    return {str(p.relative_to(tmp)): sha(p) for p in tmp.rglob("*") if p.is_file()}


def main():
    ns = load_validator_defs()
    muts = [
        ("NEG-1", "Wrong SID in batch3 pub CSV", ns["mut_wrong_sid"]),
        ("NEG-2", "Wrong DOI in batch4 pub CSV", ns["mut_wrong_doi"]),
        ("NEG-3", "Delete batch5 pub CSV", ns["mut_missing_pub_csv"]),
        ("NEG-4", "Clear all EIDs in batch1_full", ns["mut_batch1_no_eid"]),
        ("NEG-5", "Truncate source CSV to 11 lines", ns["mut_truncate_source"]),
    ]
    originals_before = {str(f.relative_to(ROOT)): sha(f) for f in required_files()}
    report = {"originals_before": originals_before, "tests": []}

    for tid, desc, fn in muts:
        tmp = make_copy()
        try:
            b_code, b_fails, b_total, _ = run(tmp)
            pre = tree_hashes(tmp)
            fn(tmp)
            post = tree_hashes(tmp)
            changed = sorted(k for k in set(pre) | set(post) if pre.get(k) != post.get(k))
            m_code, m_fails, m_total, m_out = run(tmp)
            expected_hit = [f for f in m_fails
                            if any(tok.lower() in f.lower() for tok in EXPECTED[tid])]
            crashed = "Traceback" in m_out
            ok = (b_code == 0 and not b_fails and len(changed) == 1
                  and m_code != 0 and bool(expected_hit) and not crashed)
            report["tests"].append({
                "id": tid, "mutation": desc,
                "baseline_exit": b_code, "baseline_totals": b_total,
                "baseline_fail_lines": b_fails,
                "files_changed_by_mutation": changed,
                "mutated_exit": m_code, "mutated_totals": m_total,
                "mutated_fail_lines": m_fails,
                "expected_tokens": EXPECTED[tid],
                "expected_fail_matched": expected_hit,
                "traceback": crashed,
                "verdict": "NEG-PASS" if ok else "NEG-FAIL",
            })
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    originals_after = {str(f.relative_to(ROOT)): sha(f) for f in required_files()}
    report["originals_after"] = originals_after
    report["originals_unchanged"] = originals_before == originals_after
    print(json.dumps(report, indent=2, ensure_ascii=False))
    all_ok = report["originals_unchanged"] and all(
        t["verdict"] == "NEG-PASS" for t in report["tests"])
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
