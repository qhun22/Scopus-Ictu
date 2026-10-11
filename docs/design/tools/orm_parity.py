"""So khớp ORM (SQLAlchemy) ↔ migration Alembic ↔ lược đồ PostgreSQL thật (snapshot JSON).

Không kết nối DB. Cần: Python có SQLAlchemy + alembic + các phụ thuộc của backend.
    python -X utf8 orm_parity.py --backend-dir <repo>/backend --snapshot ../database/source/schema_snapshot.json --out ../database/ORM_MIGRATION_DB_PARITY.md
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("DB_USER", "x")
os.environ.setdefault("DB_PASSWORD", "x")
os.environ.setdefault("DB_HOST", "127.0.0.1")
os.environ.setdefault("DB_PORT", "1")
os.environ.setdefault("DB_NAME", "x")
os.environ.setdefault("SECRET_KEY", "x" * 40)
os.environ.setdefault("ENVIRONMENT", "local")


def norm_type(t: str) -> str:
    t = t.lower().replace(" ", "")
    t = t.replace("charactervarying", "varchar").replace("timestampwithtimezone", "timestamptz")
    t = t.replace("timestamp(timezone=true)", "timestamptz")
    t = t.replace("doubleprecision", "float8")
    return t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend-dir", required=True)
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    backend = Path(a.backend_dir).resolve()
    sys.path.insert(0, str(backend))

    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable
    import app.models  # noqa: F401
    from app.models.base import Base
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    snap = json.load(open(a.snapshot, encoding="utf8"))
    db = snap["tables"]
    orm = Base.metadata.tables
    dialect = postgresql.dialect()

    diffs: list[str] = []
    rows: list[tuple] = []

    def add(msg: str) -> None:
        diffs.append(msg)

    orm_names, db_names = set(orm), set(db)
    for t in sorted(orm_names - db_names):
        add(f"Bảng chỉ có trong ORM: `{t}`")
    for t in sorted(db_names - orm_names):
        add(f"Bảng chỉ có trong DB: `{t}`")

    tot = dict(cols=0, pk=0, fk=0, uq=0, ck=0, ix=0)
    for t in sorted(orm_names & db_names):
        o, d = orm[t], db[t]
        ddl = str(CreateTable(o).compile(dialect=dialect))
        ocols = {c.name: c for c in o.columns}
        dcols = {c["name"]: c for c in d["columns"]}
        for n in sorted(set(ocols) - set(dcols)):
            add(f"`{t}.{n}`: có trong ORM, không có trong DB")
        for n in sorted(set(dcols) - set(ocols)):
            add(f"`{t}.{n}`: có trong DB, không có trong ORM")
        for n in sorted(set(ocols) & set(dcols)):
            oc, dc = ocols[n], dcols[n]
            ot = norm_type(oc.type.compile(dialect=dialect))
            dt_ = norm_type(dc["type"])
            if ot != dt_:
                add(f"`{t}.{n}`: kiểu ORM `{ot}` ≠ DB `{dt_}`")
            if bool(oc.nullable) != bool(dc["nullable"]):
                add(f"`{t}.{n}`: nullable ORM={oc.nullable} ≠ DB={dc['nullable']}")
            tot["cols"] += 1
        if [c.name for c in o.primary_key.columns] != d["pk"]:
            add(f"`{t}`: PK ORM {[c.name for c in o.primary_key.columns]} ≠ DB {d['pk']}")
        tot["pk"] += 1
        ofk = {(tuple(e.parent.name for e in fk.elements), fk.elements[0].column.table.name,
                tuple(e.column.name for e in fk.elements), (fk.ondelete or "NO ACTION").upper())
               for fk in o.foreign_key_constraints}
        dfk = {(tuple(f["cols"]), f["ref_table"], tuple(f["ref_cols"]), f["on_delete"]) for f in d["fks"]}
        for x in sorted(ofk - dfk):
            add(f"`{t}`: FK chỉ có ở ORM {x}")
        for x in sorted(dfk - ofk):
            add(f"`{t}`: FK chỉ có ở DB {x}")
        tot["fk"] += len(dfk)
        ouq = {tuple(c.name for c in u.columns) for u in o.constraints if u.__class__.__name__ == "UniqueConstraint"}
        duq = {tuple(u["cols"]) for u in d["uniques"]}
        for x in sorted(ouq - duq):
            add(f"`{t}`: UNIQUE chỉ có ở ORM {x}")
        for x in sorted(duq - ouq):
            add(f"`{t}`: UNIQUE chỉ có ở DB {x}")
        tot["uq"] += len(duq)
        oname = set(re.findall(r"CONSTRAINT (\S+) CHECK", ddl))
        dname = {c["name"] for c in d["checks"]}
        for x in sorted(oname - dname):
            add(f"`{t}`: CHECK chỉ có ở ORM `{x}`")
        for x in sorted(dname - oname):
            add(f"`{t}`: CHECK chỉ có ở DB `{x}`")
        tot["ck"] += len(dname)
        oix = {i.name: bool(i.unique) for i in o.indexes}
        dix = {i["name"]: i["unique"] for i in d["indexes"] if not i["primary"] and not i["backs_constraint"]}
        for x in sorted(set(oix) - set(dix)):
            add(f"`{t}`: INDEX chỉ có ở ORM `{x}`")
        for x in sorted(set(dix) - set(oix)):
            add(f"`{t}`: INDEX chỉ có ở DB `{x}`")
        for x in sorted(set(oix) & set(dix)):
            if oix[x] != dix[x]:
                add(f"`{t}`: INDEX `{x}` khác tính UNIQUE")
        tot["ix"] += len(dix)
        rows.append((t, len(dcols), len(d["fks"]), len(d["uniques"]), len(d["checks"]), len(dix)))

    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "alembic"))
    sd = ScriptDirectory.from_config(cfg)
    heads = sd.get_heads()
    chain = [r.revision for r in sd.walk_revisions()][::-1]
    db_ver = snap["meta"]["alembic_version"]
    alembic_ok = sorted(heads) == sorted(db_ver)
    if not alembic_ok:
        add(f"Alembic head {heads} ≠ alembic_version trong DB {db_ver}")

    L = []
    L.append("# So khớp ORM ↔ Alembic ↔ PostgreSQL thật\n")
    L.append("> Tệp **sinh tự động** bởi `docs/design/tools/orm_parity.py` — không sửa tay. "
             f"Snapshot: DB `{snap['meta']['database']}` (PostgreSQL {snap['meta']['postgres_version']}), "
             f"trích lúc `{snap['meta']['extracted_at']}` ở chế độ chỉ đọc.\n")
    L.append("## 1. Kết luận\n")
    verdict = "KHỚP HOÀN TOÀN" if not diffs else f"CÓ {len(diffs)} CHÊNH LỆCH"
    L.append(f"**{verdict}** giữa ORM (`backend/app/models`) và DB trên các mặt: tên bảng, tên/kiểu/NULL của cột, PK, FK (cột, bảng tham chiếu, ON DELETE), "
             "UNIQUE, tên CHECK và tên chỉ mục.\n")
    L.append(f"- Bảng: ORM {len(orm_names)} · DB {len(db_names)} · giao nhau {len(orm_names & db_names)}")
    L.append(f"- Cột đã so: {tot['cols']} · PK: {tot['pk']} · FK: {tot['fk']} · UNIQUE: {tot['uq']} · CHECK: {tot['ck']} · INDEX thường/partial: {tot['ix']}")
    L.append(f"- Alembic: head trong `alembic/versions` = `{', '.join(heads)}`; `alembic_version` trong DB = `{', '.join(db_ver)}` → "
             + ("**khớp**" if alembic_ok else "**LỆCH**"))
    L.append(f"- Chuỗi migration (cũ → mới): `{' → '.join(chain)}` ({len(chain)} bản, tuyến tính)\n")
    L.append("### Giới hạn của phép so khớp\n")
    L.append("- **Biểu thức CHECK** chỉ so theo *tên* (PostgreSQL chuẩn hóa lại biểu thức nên không so chuỗi). Nội dung từng CHECK lấy từ DB, xem `CONSTRAINTS_CATALOG.md`.")
    L.append("- **DEFAULT/server_default** và **comment** không được so.")
    L.append("- **Chưa chạy `alembic upgrade head` trên DB trống** để so migration ↔ DB (Task 19 cấm migration). Việc kiểm migration chỉ ở mức: chuỗi revision tuyến tính, head = `alembic_version` của DB thật.\n")
    L.append("## 2. Chi tiết chênh lệch\n")
    if diffs:
        L.extend(f"- {d}" for d in diffs)
    else:
        L.append("Không có chênh lệch.")
    L.append("\n### Giải thích các chênh lệch đã biết (ghi tay, đã kiểm tra mã nguồn)\n")
    if any("normalization_summa_5872" in d for d in diffs):
        L.append("- `scopus_imports` — CHECK `ck_scopus_imports_ck_scopus_imports_normalization_summa_5872`: do migration `f4c8b1a2e9d7` "
                 "(`op.create_check_constraint(\"ck_scopus_imports_normalization_summary_object\", …)`) tạo ra; quy ước đặt tên `ck_%(table_name)s_%(constraint_name)s` "
                 "được áp thêm một lần nữa nên tên vật lý bị lặp tiền tố và rút gọn kèm hậu tố băm `_5872`. **Mô hình ORM `ScopusImport` không khai báo CHECK này** "
                 "(`backend/app/models/scopus_raw.py`, cột `normalization_summary`). Hệ quả: DB có ràng buộc `normalization_summary` phải là JSON object hoặc NULL; "
                 "ORM không phản ánh. Đây là *lệch ORM ↔ migration*, không ảnh hưởng dữ liệu hiện có. **Không sửa trong Task 19** (cấm đổi mã/migration); ghi nhận để sửa sau.")
    L.append("\n## 3. Thống kê theo bảng (từ DB)\n")
    L.append("| Bảng | Cột | FK | UNIQUE (ràng buộc) | CHECK | INDEX (thường/partial) |")
    L.append("|---|--:|--:|--:|--:|--:|")
    for r in rows:
        L.append("| `{}` | {} | {} | {} | {} | {} |".format(*r))
    L.append("| **Tổng** | **{}** | **{}** | **{}** | **{}** | **{}** |".format(
        sum(r[1] for r in rows), sum(r[2] for r in rows), sum(r[3] for r in rows), sum(r[4] for r in rows), sum(r[5] for r in rows)))
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf8")
    print(verdict, "| diffs:", len(diffs))
    for d in diffs[:40]:
        print(" -", d)
    return 0 if not diffs else 1


if __name__ == "__main__":
    raise SystemExit(main())
