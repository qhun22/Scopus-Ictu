"""Evaluate the lecturer <-> Scopus-author suggestions against a reference set. Read-only.

    python -m scripts.evaluate_candidates [--reference PATH] [--out DIR]

Reference set: the ICTU "Scopus account merge guide" saved as JSON (see ``services/merge_guide``),
which lists, per lecturer e-mail, the Scopus IDs the school itself associates with that person.
It is the school's statement, not a verdict confirmed by the thesis supervisor, and it only covers
lecturers with TWO OR MORE IDs, so the figures describe that group and must be reported as such.

Measures, over lecturers present in both the reference and the system:
* recall     : reference IDs that exist in the Scopus data AND were proposed as candidates
* precision  : proposed candidates (of those lecturers) that the reference confirms
* by degree of fit : precision per HIGH / MEDIUM / LOW / INSUFFICIENT
* coverage   : reference IDs absent from the imported Scopus data (they cannot be proposed)

Only aggregate numbers are written; personal data stays in the database and the reference file.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.v1.endpoints.reviews import _queue_statement
from app.models.master_lecturer import Lecturer
from app.models.publication import ScopusAuthor
from app.services.candidate_fit import assess_fit, ictu_affiliation_paper_counts
from scripts import demo_launcher as dl

_FIT_ORDER = ("HIGH", "MEDIUM", "LOW", "INSUFFICIENT")


def _engine():
    values = dl.read_env_file(dl.ENV_FILE)
    problems = dl.validate_config(values)
    if problems:
        raise SystemExit("Cau hinh khong hop le: " + "; ".join(problems))
    url = (
        f"postgresql+psycopg2://{values['DB_USER']}:{values['DB_PASSWORD']}"
        f"@127.0.0.1:{dl.PG_PORT}/{values['DB_NAME']}"
    )
    return create_engine(url), values["DB_NAME"]


def evaluate(session: Session, reference: dict) -> dict:
    by_email = {e["email"].lower(): set(e["scopus_ids"]) for e in reference["entries"]}
    lecturers = {
        (email or "").lower(): lid
        for lid, email in session.execute(select(Lecturer.id, Lecturer.email)).all()
    }
    in_both = {email: ids for email, ids in by_email.items() if email in lecturers}
    known_ids = set(session.scalars(select(ScopusAuthor.scopus_id)).all())

    rows = session.execute(_queue_statement(
        candidate_status="PENDING", evidence_category=None, ambiguity=None,
    )).mappings().all()
    ictu_papers = ictu_affiliation_paper_counts(session, {r["scopus_author_id"] for r in rows})
    lecturer_email = {lid: email for email, lid in lecturers.items()}

    proposed: dict[str, set[str]] = defaultdict(set)
    fit_total: Counter = Counter()
    fit_confirmed: Counter = Counter()
    for row in rows:
        email = lecturer_email.get(row["lecturer_id"])
        if email not in in_both:
            continue
        fit = assess_fit(
            name_evidence_count=int(row["name_evidence_count"]),
            publication_support_count=int(row["publication_support_count"]),
            ictu_affiliation_papers=ictu_papers.get(row["scopus_author_id"], 0),
            is_shared_author=int(row["candidate_count_for_scopus_author"]) > 1,
            is_ambiguous_lecturer=int(row["candidate_count_for_lecturer"]) > 1,
        ).level
        proposed[email].add(row["scopus_id"])
        fit_total[fit] += 1
        if row["scopus_id"] in in_both[email]:
            fit_confirmed[fit] += 1

    reference_pairs = sum(len(ids) for ids in in_both.values())
    present_pairs = sum(len(ids & known_ids) for ids in in_both.values())
    found_pairs = sum(len(ids & proposed.get(email, set())) for email, ids in in_both.items())
    proposed_pairs = sum(len(p) for p in proposed.values())
    confirmed_pairs = sum(len(p & in_both[email]) for email, p in proposed.items())

    def ratio(a: int, b: int) -> float | None:
        return round(a / b, 3) if b else None

    return {
        "reference_lecturers": len(by_email),
        "lecturers_in_both": len(in_both),
        "reference_pairs": reference_pairs,
        "reference_pairs_present_in_scopus_data": present_pairs,
        "coverage": ratio(present_pairs, reference_pairs),
        "proposed_pairs_for_these_lecturers": proposed_pairs,
        "confirmed_by_reference": confirmed_pairs,
        "precision": ratio(confirmed_pairs, proposed_pairs),
        "reference_pairs_proposed": found_pairs,
        "recall_over_present_ids": ratio(found_pairs, present_pairs),
        "by_fit": {
            level: {
                "proposed": fit_total[level],
                "confirmed": fit_confirmed[level],
                "precision": ratio(fit_confirmed[level], fit_total[level]),
            }
            for level in _FIT_ORDER
        },
    }


def render(result: dict, database: str, reference_path: Path) -> str:
    def pct(value: float | None) -> str:
        return "n/a" if value is None else f"{value * 100:.1f}%"

    lines = [
        "# Đánh giá chất lượng gợi ý ánh xạ giảng viên ↔ tác giả Scopus",
        "",
        f"- Thời điểm: {datetime.now().strftime('%Y-%m-%d %H:%M')} · database: `{database}`",
        f"- Tập đối chiếu: `{reference_path.name}` (danh sách gộp tài khoản Scopus của ICTU).",
        "- **Giới hạn:** đây là lời khai của nhà trường, chưa phải tập đối chiếu do GVHD xác nhận, và chỉ gồm",
        "  giảng viên có từ 2 ID trở lên. Số liệu chỉ mô tả nhóm này, không suy ra cho toàn bộ giảng viên.",
        "",
        "## Kết quả",
        "",
        "| Chỉ số | Giá trị |",
        "|---|---|",
        f"| Giảng viên trong tập đối chiếu / có trong hệ thống | {result['reference_lecturers']} / {result['lecturers_in_both']} |",
        f"| Cặp (giảng viên, ID) trong tập đối chiếu | {result['reference_pairs']} |",
        f"| Trong đó ID có trong dữ liệu Scopus đã nhập (độ phủ dữ liệu) | {result['reference_pairs_present_in_scopus_data']} ({pct(result['coverage'])}) |",
        f"| Cặp được hệ thống đề xuất cho các giảng viên này | {result['proposed_pairs_for_these_lecturers']} |",
        f"| Trong đó được tập đối chiếu xác nhận (độ chính xác) | {result['confirmed_by_reference']} ({pct(result['precision'])}) |",
        f"| Cặp đối chiếu mà hệ thống đã đề xuất (độ phủ, trên ID có dữ liệu) | {result['reference_pairs_proposed']} ({pct(result['recall_over_present_ids'])}) |",
        "",
        "## Độ chính xác theo mức phù hợp",
        "",
        "| Mức | Đề xuất | Được xác nhận | Độ chính xác |",
        "|---|---|---|---|",
    ]
    for level in _FIT_ORDER:
        row = result["by_fit"][level]
        lines.append(f"| {level} | {row['proposed']} | {row['confirmed']} | {pct(row['precision'])} |")
    lines += [
        "",
        "Hệ thống không tự gộp: các số trên đo chất lượng **gợi ý** để người duyệt xem, không phải quyết định.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    default_reference = dl.REPO / "data" / "lecturers" / "raw" / "merge_guide.json"
    parser.add_argument("--reference", type=Path, default=default_reference)
    parser.add_argument("--out", type=Path, default=dl.DOAN / "_quan_ly_do_an" / "evidence")
    args = parser.parse_args(argv)
    if not args.reference.exists():
        print(f"[LOI] Khong thay tap doi chieu: {args.reference}")
        return 1
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    engine, database = _engine()
    with Session(engine) as session:
        result = evaluate(session, reference)
    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    (args.out / f"danh_gia_goi_y_{stamp}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    report = args.out / f"danh_gia_goi_y_{stamp}.md"
    report.write_text(render(result, database, args.reference), encoding="utf-8")
    print(report.read_text(encoding="utf-8"))
    print(f"[OK] Da ghi: {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
