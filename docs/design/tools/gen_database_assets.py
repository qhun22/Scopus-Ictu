"""Sinh tài sản thiết kế CSDL từ snapshot lược đồ thật (không kết nối DB).

Đầu vào : docs/design/database/source/schema_snapshot.json  (từ extract_schema.py)
          docs/design/database/source/descriptions_vi.json   (mô tả nghiệp vụ biên soạn tay)
Đầu ra  : DATA_DICTIONARY.md/.csv, KEYS_RELATIONS.md, CONSTRAINTS_CATALOG.md,
          erd/*.puml, erd/scopus_ictu.dbml, class/*.puml

    python -X utf8 gen_database_assets.py
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

DESIGN = Path(__file__).resolve().parents[1]
DB = DESIGN / "database"
SNAP = json.load(open(DB / "source" / "schema_snapshot.json", encoding="utf8"))
DESC = json.load(open(DB / "source" / "descriptions_vi.json", encoding="utf8"))
T = SNAP["tables"]
CLUSTERS = DESC["clusters"]
GEN = DESC["generic_columns"]
TABLE_CLUSTER = {t: k for k, c in CLUSTERS.items() for t in c["tables"]}
assert set(TABLE_CLUSTER) == set(T), "mô tả cụm không khớp danh sách bảng"

CLUSTER_COLOR = {"A": "#E8DAEF", "B": "#FCF3CF", "C": "#D5F5E3", "D": "#D6EAF8", "E": "#FADBD8", "F": "#FDEBD0"}
CLUSTER_SLUG = {"A": "A_nguoi_dung_kiem_toan", "B": "B_ho_so_giang_vien", "C": "C_nhap_tho_scopus",
                "D": "D_cong_bo_tac_gia", "E": "E_don_vi_cong_tac", "F": "F_doi_soat_danh_tinh"}


def short_type(t: str) -> str:
    return (t.replace("character varying", "varchar").replace("timestamp with time zone", "timestamptz")
            .replace("character", "char"))


def partial_uniques(t: str):
    return [i for i in T[t]["indexes"] if i["unique"] and not i["primary"] and not i["backs_constraint"]]


def idx_cols(i):
    """Cột (hoặc biểu thức) của chỉ mục từ định nghĩa."""
    m = re.search(r"\((.*?)\)(?: WHERE|$)", i["definition"])
    return m.group(1) if m else ""


def fk_rows():
    rows = []
    for child, info in sorted(T.items()):
        uq_sets = [tuple(u["cols"]) for u in info["uniques"]]
        pu_sets = []
        for i in partial_uniques(child):
            pu_sets.append(tuple(c.strip() for c in idx_cols(i).split(",")))
        for fk in info["fks"]:
            cols = tuple(fk["cols"])
            col_info = {c["name"]: c for c in info["columns"]}
            not_null = all(not col_info[c]["nullable"] for c in cols)
            unique = cols in uq_sets or cols in pu_sets
            rows.append(dict(
                name=fk["name"], child=child, cols=list(cols), parent=fk["ref_table"], pcols=fk["ref_cols"],
                on_delete=fk["on_delete"], parent_mult="1" if not_null else "0..1",
                child_mult="0..1" if unique else "0..*",
                unique_kind=("UNIQUE" if cols in uq_sets else ("UNIQUE một phần" if cols in pu_sets else "")),
            ))
    return rows


FKS = fk_rows()
assert len(FKS) == sum(len(v["fks"]) for v in T.values())


def pk_set(t):
    return set(T[t]["pk"])


def fk_cols(t):
    return {c for fk in T[t]["fks"] for c in fk["cols"]}


def uq_cols(t):
    s = set()
    for u in T[t]["uniques"]:
        if len(u["cols"]) == 1:
            s.add(u["cols"][0])
    return s


# ----------------------------------------------------------------------------- Data dictionary
def col_marks(t, c):
    marks = []
    if c in pk_set(t):
        marks.append("PK")
    for fk in T[t]["fks"]:
        if c in fk["cols"]:
            marks.append("FK→`{}.{}`".format(fk["ref_table"], fk["ref_cols"][fk["cols"].index(c)]))
    for u in T[t]["uniques"]:
        if c in u["cols"]:
            marks.append("UQ" if len(u["cols"]) == 1 else "UQ(" + ",".join(u["cols"]) + ")")
    for i in partial_uniques(t):
        cols = [x.strip() for x in idx_cols(i).split(",")]
        if c in cols or any(c in x for x in cols):
            marks.append("UQ một phần")
    return marks


def related_checks(t, c):
    out = []
    for ck in T[t]["checks"]:
        if re.search(rf"\b{re.escape(c)}\b", ck["expr"]):
            short = ck["name"].replace(f"ck_{t}_", "")
            out.append(short)
    return out


def col_desc(t, c):
    d = DESC["tables"][t].get("columns", {}).get(c)
    if d:
        return d
    if c in GEN:
        return GEN[c]
    raise KeyError(f"thiếu mô tả cột {t}.{c}")


def build_dictionary():
    csv_rows = []
    L = []
    meta = SNAP["meta"]
    L.append("# Data Dictionary — 24 bảng PostgreSQL của Scopus–ICTU\n")
    L.append("> **Sinh tự động** từ lược đồ PostgreSQL thật bằng `docs/design/tools/gen_database_assets.py` (cấu trúc) + `database/source/descriptions_vi.json` (mô tả nghiệp vụ, biên soạn tay). "
             f"Nguồn cấu trúc: DB `{meta['database']}` (PostgreSQL {meta['postgres_version']}, `alembic_version = {', '.join(meta['alembic_version'])}`), trích lúc `{meta['extracted_at']}` ở chế độ **chỉ đọc**. "
             "Số dòng là số đếm tại thời điểm trích (dữ liệu demo teacher), **không phải dữ liệu thật của ICTU**.\n")
    tot_cols = sum(len(v["columns"]) for v in T.values())
    L.append(f"**Phạm vi:** {len(T)} bảng · {tot_cols} cột · {sum(len(v['fks']) for v in T.values())} khóa ngoại · "
             f"{sum(len(v['checks']) for v in T.values())} CHECK. Không có trigger, hàm hay view do dự án định nghĩa (trigger = {meta['triggers']}, hàm = {meta['functions']}).\n")
    L.append("**Chú giải:** `PK` khóa chính · `FK→bảng.cột` khóa ngoại · `UQ` duy nhất · `UQ một phần` chỉ mục unique có điều kiện (partial) · "
             "`NULL` = cho phép NULL. Mọi khóa chính là `uuid` mặc định `gen_random_uuid()`; mọi mốc thời gian là `timestamptz`.\n")
    L.append("## Mục lục\n")
    L.append("| Cụm | Bảng | Số cột | Số dòng (demo) |")
    L.append("|---|---|--:|--:|")
    for k, c in CLUSTERS.items():
        for t in c["tables"]:
            L.append(f"| {k}. {c['name']} | [`{t}`](#{t}) | {len(T[t]['columns'])} | {T[t]['row_count']} |")
    L.append("")
    for k, c in CLUSTERS.items():
        L.append(f"## Cụm {k} — {c['name']}\n")
        for t in c["tables"]:
            d = DESC["tables"][t]
            L.append(f"### {t}\n")
            L.append(f"**{d['title']}.** {d['desc']}\n")
            L.append(f"- Cụm: **{k}** · Số dòng demo: **{T[t]['row_count']}** · UC liên quan: {d['uc']}")
            L.append(f"- Khóa chính: `{', '.join(T[t]['pk'])}`")
            if T[t]["fks"]:
                L.append("- Khóa ngoại: " + "; ".join(
                    f"`{','.join(fk['cols'])}` → `{fk['ref_table']}({','.join(fk['ref_cols'])})` (ON DELETE {fk['on_delete']})" for fk in T[t]["fks"]))
            L.append("")
            L.append("| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |")
            L.append("|--:|---|---|:-:|---|---|---|")
            for n, col in enumerate(T[t]["columns"], 1):
                name = col["name"]
                marks = col_marks(t, name)
                cks = related_checks(t, name)
                kc = ", ".join(marks)
                if cks:
                    kc = (kc + "; " if kc else "") + "CHECK: " + ", ".join(f"`{x}`" for x in cks)
                default = (col["default"] or "").replace("|", "\\|")
                desc = col_desc(t, name).replace("|", "\\|")
                L.append(f"| {n} | `{name}` | `{short_type(col['type'])}` | {'có' if col['nullable'] else 'không'} | {('`' + default + '`') if default else ''} | {kc} | {desc} |")
                csv_rows.append([k, t, n, name, short_type(col["type"]), "YES" if col["nullable"] else "NO", col["default"] or "",
                                 "; ".join(marks), "; ".join(cks), col_desc(t, name)])
            ux = T[t]["uniques"]
            pu = partial_uniques(t)
            if ux or pu:
                L.append("")
                L.append("**Ràng buộc duy nhất:** " + "; ".join(
                    [f"`{u['name']}` ({', '.join(u['cols'])})" for u in ux] +
                    [f"`{i['name']}` ({idx_cols(i)}) WHERE {i['predicate']}" for i in pu]))
            ixs = [i for i in T[t]["indexes"] if not i["primary"] and not i["backs_constraint"] and not i["unique"]]
            if ixs:
                L.append("")
                L.append("**Chỉ mục:** " + "; ".join(
                    f"`{i['name']}` ({idx_cols(i)}){' WHERE ' + i['predicate'] if i['predicate'] else ''}" for i in ixs))
            L.append("")
    (DB / "DATA_DICTIONARY.md").write_text("\n".join(L) + "\n", encoding="utf8")
    with open(DB / "DATA_DICTIONARY.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["cum", "bang", "stt", "cot", "kieu", "null", "mac_dinh", "khoa_rang_buoc", "check_lien_quan", "mo_ta"])
        w.writerows(csv_rows)


# ----------------------------------------------------------------------------- Keys / relations
def build_keys():
    L = []
    L.append("# Bảng khóa chính, khóa ngoại, duy nhất và chỉ mục\n")
    L.append("> **Sinh tự động** từ snapshot lược đồ thật (`gen_database_assets.py`). Cardinality suy ra như sau: phía **cha** là `1` nếu cột FK `NOT NULL`, ngược lại `0..1`; "
             "phía **con** là `0..1` nếu cột FK là duy nhất (UNIQUE hoặc chỉ mục unique một phần), ngược lại `0..*`.\n")
    L.append(f"## 1. Khóa ngoại ({len(FKS)})\n")
    L.append("| # | Cụm | Bảng con (cột) | → | Bảng cha (cột) | Cardinality (cha : con) | ON DELETE | Tên ràng buộc |")
    L.append("|--:|:-:|---|:-:|---|:-:|---|---|")
    for n, f in enumerate(sorted(FKS, key=lambda x: (TABLE_CLUSTER[x["child"]], x["child"], x["cols"])), 1):
        extra = f" ({f['unique_kind']})" if f["unique_kind"] else ""
        comp = " — FK ghép" if len(f["cols"]) > 1 else ""
        L.append(f"| {n} | {TABLE_CLUSTER[f['child']]} | `{f['child']}` (`{', '.join(f['cols'])}`){comp} | → | `{f['parent']}` (`{', '.join(f['pcols'])}`) | "
                 f"{f['parent_mult']} : {f['child_mult']}{extra} | {f['on_delete']} | `{f['name']}` |")
    L.append("")
    cas = [f for f in FKS if f["on_delete"] == "CASCADE"]
    L.append(f"- **ON DELETE CASCADE ({len(cas)}):** " + "; ".join(f"`{f['parent']}` → `{f['child']}`" for f in cas) +
             ". Mọi khóa ngoại còn lại là `RESTRICT`: không thể xóa bản ghi đang được tham chiếu.")
    comp = [f for f in FKS if len(f["cols"]) > 1]
    L.append(f"- **Khóa ngoại ghép ({len(comp)}):** " + "; ".join(f"`{f['child']}({', '.join(f['cols'])})` → `{f['parent']}({', '.join(f['pcols'])})`" for f in comp) + ".")
    L.append("")
    L.append(f"## 2. Khóa chính ({sum(1 for v in T.values() if v['pk'])})\n")
    L.append("| Bảng | Khóa chính | Tên ràng buộc |")
    L.append("|---|---|---|")
    for t in sorted(T):
        pkname = next(i["name"] for i in T[t]["indexes"] if i["primary"])
        L.append(f"| `{t}` | `{', '.join(T[t]['pk'])}` | `{pkname}` |")
    L.append("")
    n_u = sum(len(v["uniques"]) for v in T.values())
    L.append(f"## 3. Ràng buộc UNIQUE ({n_u})\n")
    L.append("| Bảng | Tên | Cột | Ý nghĩa chống trùng |")
    L.append("|---|---|---|---|")
    meaning = {
        "uq_author_name_variants": "Một dạng tên chỉ lưu một lần cho mỗi tác giả.",
        "uq_candidate_evidence_descriptor": "Cùng một bằng chứng (luật, phiên bản, dấu vân tay) không lưu hai lần trong một quan sát.",
        "uq_candidate_observations_candidate_run": "Mỗi ứng viên chỉ có một quan sát trong một lần chạy.",
        "uq_identity_evidence_dedup": "Không lưu trùng bằng chứng của cùng một danh tính.",
        "uq_lecturer_scopus_candidates_pair": "Mỗi cặp (giảng viên, tác giả Scopus) chỉ là một ứng viên.",
        "uq_lecturer_scopus_identities_pair": "Mỗi cặp (giảng viên, tác giả Scopus) chỉ có một danh tính.",
        "uq_lecturer_source_snapshots_id_lecturer": "Khóa ứng viên ghép (id, lecturer_id) để làm đích cho FK ghép của công bố đã biết.",
        "uq_paa_resolution_ord": "Thứ tự đơn vị là duy nhất trong một resolution.",
        "uq_paar_author_source_payload": "Cùng vị trí tác giả + nguồn + payload (SHA-256) chỉ nạp một lần (nhập lại không trùng).",
        "uq_paar_id_link_status": "Khóa ứng viên ghép (id, link_status) làm đích cho FK ghép của dòng đơn vị.",
        "uq_publication_authors_author": "Một tác giả chỉ xuất hiện một lần trong một công bố.",
        "uq_publication_authors_order": "Mỗi thứ tự tác giả trong công bố chỉ thuộc một người.",
        "uq_publication_raw_sources_raw_record_id": "Mỗi dòng thô chỉ dẫn tới tối đa một công bố (provenance 1–1 phía dòng thô).",
        "uq_publications_eid": "Mỗi EID chỉ một công bố chuẩn hóa — chốt chặn chống trùng công bố.",
        "uq_raw_scopus_records_import_row": "Mỗi số dòng chỉ xuất hiện một lần trong một đợt nhập.",
        "uq_scopus_authors_scopus_id": "Mỗi Scopus Author ID chỉ một tác giả.",
    }
    for t in sorted(T):
        for u in T[t]["uniques"]:
            L.append(f"| `{t}` | `{u['name']}` | `{', '.join(u['cols'])}` | {meaning.get(u['name'], '')} |")
    L.append("")
    pus = [(t, i) for t in sorted(T) for i in partial_uniques(t)]
    L.append(f"## 4. Chỉ mục UNIQUE một phần (partial) ({len(pus)})\n")
    L.append("| Bảng | Tên | Biểu thức/cột | Điều kiện | Ý nghĩa |")
    L.append("|---|---|---|---|---|")
    pmeaning = {
        "uq_identities_scopus_author_approved": "**Một Scopus Author ID chỉ được APPROVED cho đúng một giảng viên** — chặn gán trùng ở mức DB.",
        "uq_lecturers_orcid": "ORCID duy nhất khi có.",
        "uq_lecturers_staff_code": "Mã cán bộ duy nhất khi có.",
        "uq_organizations_source_name": "Tổ chức không có mã nguồn thì duy nhất theo (nguồn, tên).",
        "uq_organizations_source_org": "Tổ chức có mã nguồn thì duy nhất theo (nguồn, mã).",
        "uq_users_email_ci": "Email tài khoản duy nhất, không phân biệt hoa/thường.",
        "uq_users_lecturer": "Mỗi hồ sơ giảng viên tối đa một tài khoản (quan hệ 0..1).",
    }
    for t, i in pus:
        L.append(f"| `{t}` | `{i['name']}` | `{idx_cols(i)}` | `{i['predicate']}` | {pmeaning.get(i['name'], '')} |")
    L.append("")
    nonu = [(t, i) for t in sorted(T) for i in T[t]["indexes"] if not i["primary"] and not i["backs_constraint"] and not i["unique"]]
    L.append(f"## 5. Chỉ mục thường ({len(nonu)})\n")
    L.append("| Bảng | Tên | Cột/biểu thức | Điều kiện (partial) |")
    L.append("|---|---|---|---|")
    for t, i in nonu:
        L.append(f"| `{t}` | `{i['name']}` | `{idx_cols(i)}` | {('`' + i['predicate'] + '`') if i['predicate'] else ''} |")
    L.append("")
    L.append("**Lưu ý:** các cột khóa ngoại thường có chỉ mục hỗ trợ truy vấn; một số FK không có chỉ mục riêng vì đã nằm đầu một ràng buộc UNIQUE ghép. "
             "Task 19 không đo hiệu năng nên **không khẳng định** bộ chỉ mục là tối ưu.\n")
    (DB / "KEYS_RELATIONS.md").write_text("\n".join(L) + "\n", encoding="utf8")


# ----------------------------------------------------------------------------- CHECK catalog
def build_checks():
    L = []
    n = sum(len(v["checks"]) for v in T.values())
    L.append("# Danh mục ràng buộc CHECK (99)\n".replace("99", str(n)))
    L.append("> **Sinh tự động** từ `pg_get_constraintdef` của DB thật. Nhóm phân loại do `gen_database_assets.py` suy từ tên/biểu thức; "
             "giải thích nghiệp vụ của các ràng buộc quan trọng nằm ở `CONSTRAINTS_BUSINESS_RULES.md`.\n")

    def group(ck):
        e, nme = ck["expr"], ck["name"]
        if "jsonb_typeof" in e:
            return "Kiểu JSONB (object/array)"
        if "~ '^[0-9a-f]{64}$'" in e:
            return "Định dạng SHA-256"
        if "= ANY" in e and "ARRAY" in e and "transition" not in nme:
            return "Từ vựng giá trị (enumeration)"
        if "btrim" in e:
            return "Không rỗng"
        if "transitions" in nme:
            return "Bảng chuyển trạng thái"
        if ">=" in e or "<=" in e:
            return "Miền giá trị số"
        if "~" in e:
            return "Định dạng chuỗi"
        return "Nhất quán nghiệp vụ giữa các cột"

    groups: dict[str, list] = {}
    for t in sorted(T):
        for ck in T[t]["checks"]:
            groups.setdefault(group(ck), []).append((t, ck))
    L.append("## Tổng hợp theo nhóm\n")
    L.append("| Nhóm | Số CHECK |")
    L.append("|---|--:|")
    for g, v in sorted(groups.items(), key=lambda x: -len(x[1])):
        L.append(f"| {g} | {len(v)} |")
    L.append(f"| **Tổng** | **{n}** |\n")
    for g, v in sorted(groups.items(), key=lambda x: -len(x[1])):
        L.append(f"## {g} ({len(v)})\n")
        L.append("| Bảng | Tên | Biểu thức (PostgreSQL) |")
        L.append("|---|---|---|")
        for t, ck in v:
            expr = ck["expr"].replace("|", "\\|").replace("\n", " ")
            L.append(f"| `{t}` | `{ck['name']}` | `{expr}` |")
        L.append("")
    (DB / "CONSTRAINTS_CATALOG.md").write_text("\n".join(L) + "\n", encoding="utf8")


# ----------------------------------------------------------------------------- PlantUML ERD
PUML_HEAD = """@startuml {name}
' Nguồn: docs/design/database/source/schema_snapshot.json (sinh bởi tools/gen_database_assets.py) — KHÔNG sửa tay phần sinh tự động.
skinparam dpi 160
skinparam defaultFontName "Segoe UI"
skinparam defaultFontSize 12
skinparam shadowing false
skinparam linetype polyline
skinparam nodesep 40
skinparam ranksep 60
skinparam entity {{
  BackgroundColor #FFFFFF
  BorderColor #34495E
  FontSize 12
  AttributeFontSize 11
}}
skinparam ArrowColor #34495E
skinparam ArrowFontSize 10
skinparam packageStyle rectangle
hide circle
"""


def rel_symbols(f):
    left = "||" if f["parent_mult"] == "1" else "|o"
    right = "o|" if f["child_mult"] == "0..1" else "o{"
    return f"{left}--{right}"


def entity_block(t, full=True, stub=False):
    color = CLUSTER_COLOR[TABLE_CLUSTER[t]]
    if stub:
        pk = T[t]["pk"][0]
        return f'entity "{t}" as {t} #EEEEEE {{\n  *{pk} : uuid <<PK>>\n  ..\n  (bảng thuộc cụm {TABLE_CLUSTER[t]})\n}}\n'
    lines = [f'entity "{t}" as {t} {color} {{']
    pks = pk_set(t)
    fkc = fk_cols(t)
    for c in T[t]["columns"]:
        if c["name"] in pks:
            lines.append(f"  *{c['name']} : {short_type(c['type'])} <<PK>>")
    lines.append("  --")
    for c in T[t]["columns"]:
        if c["name"] in pks:
            continue
        mark = " <<FK>>" if c["name"] in fkc else ""
        uq = " <<UQ>>" if c["name"] in uq_cols(t) else ""
        star = "" if c["nullable"] else "*"
        lines.append(f"  {star}{c['name']} : {short_type(c['type'])}{mark}{uq}")
    lines.append("}\n")
    return "\n".join(lines)


def write_puml(path, name, body, title):
    txt = PUML_HEAD.format(name=name) + f'title {title}\n\n' + body + "\n@enduml\n"
    Path(path).write_text(txt, encoding="utf8")


def legend_er():
    return ("legend bottom right\n"
            "  <b>Chú giải</b>\n"
            "  * = NOT NULL · <<PK>> khóa chính · <<FK>> khóa ngoại · <<UQ>> duy nhất\n"
            "  Đầu nối (crow's foot): hai gạch = đúng 1 · vòng tròn + gạch = 0..1 · vòng tròn + chân chim = 0..*\n"
            "  Nhãn trên đường nối = cột khóa ngoại ở bảng con\n"
            "  Nguồn: PostgreSQL thật (alembic a9c2e4f71b30)\n"
            "endlegend\n")


def build_erds():
    erd = DB / "erd"
    # ERD-0: tổng thể — chỉ tên bảng (+ PK) theo cụm
    body = ["left to right direction"]
    for k, c in CLUSTERS.items():
        body.append(f'package "Cụm {k} – {c["name"]}" {CLUSTER_COLOR[k]} {{')
        for t in c["tables"]:
            body.append(f'  entity "{t}" as {t} {CLUSTER_COLOR[k]} {{\n    *id : uuid <<PK>>\n  }}')
        body.append("}")
    for f in FKS:
        lab = ", ".join(f["cols"])
        body.append(f'{f["parent"]} {rel_symbols(f)} {f["child"]} : {lab}')
    body.append(legend_er())
    write_puml(erd / "ERD-0_tong_the.puml", "ERD-0_tong_the", "\n".join(body),
               "ERD-0 — Toàn bộ CSDL Scopus–ICTU (24 bảng, 30 khóa ngoại)")
    # ERD cụm
    for k, c in CLUSTERS.items():
        tabs = set(c["tables"])
        stubs = set()
        rels = []
        for f in FKS:
            if f["child"] in tabs or f["parent"] in tabs:
                rels.append(f)
                for x in (f["child"], f["parent"]):
                    if x not in tabs:
                        stubs.add(x)
        body = ["left to right direction"] if k in ("A",) else []
        for t in c["tables"]:
            body.append(entity_block(t))
        for s in sorted(stubs):
            body.append(entity_block(s, stub=True))
        for f in rels:
            body.append(f'{f["parent"]} {rel_symbols(f)} {f["child"]} : {", ".join(f["cols"])}')
        body.append(legend_er())
        write_puml(erd / f"ERD-{CLUSTER_SLUG[k]}.puml", f"ERD-{CLUSTER_SLUG[k]}", "\n".join(body),
                   f"ERD-{k} — Cụm {k}: {c['name']}")
    # DBML
    out = ["// Scopus–ICTU — lược đồ PostgreSQL thật (alembic a9c2e4f71b30). SINH TỰ ĐỘNG từ schema_snapshot.json.",
           "// Dán vào https://dbdiagram.io để xem/chỉnh. Không sửa quan hệ nếu không đổi DB thật.", "",
           "Project scopus_ictu {", "  database_type: 'PostgreSQL'", "}", ""]
    for k, c in CLUSTERS.items():
        out.append(f"// ===== Cụm {k}: {c['name']} =====")
        for t in c["tables"]:
            out.append(f"Table {t} {{")
            for col in T[t]["columns"]:
                attrs = []
                if col["name"] in pk_set(t):
                    attrs.append("pk")
                if not col["nullable"] and col["name"] not in pk_set(t):
                    attrs.append("not null")
                if col["name"] in uq_cols(t):
                    attrs.append("unique")
                if col["default"]:
                    d = col["default"].replace("'", "\\'")
                    attrs.append(f"default: '{d}'")
                note = col_desc(t, col["name"]).replace("'", "\\'")
                attrs.append(f"note: '{note}'")
                out.append(f"  {col['name']} {short_type(col['type']).replace(' ', '_')} [{', '.join(attrs)}]")
            idxs = []
            for u in T[t]["uniques"]:
                if len(u["cols"]) > 1:
                    idxs.append(f"    ({', '.join(u['cols'])}) [unique, name: '{u['name']}']")
            if idxs:
                out.append("  indexes {")
                out.extend(idxs)
                out.append("  }")
            out.append(f"  Note: '{DESC['tables'][t]['title']}'")
            out.append("}")
            out.append("")
    out.append("// ===== Quan hệ (30 khóa ngoại) =====")
    for f in FKS:
        if len(f["cols"]) == 1:
            sym = "-" if f["child_mult"] == "0..1" else ">"
            # DBML: child.col > parent.col  (nhiều–một)
            out.append(f"Ref {f['name'][:60].replace('-', '_')}: {f['child']}.{f['cols'][0]} {sym} {f['parent']}.{f['pcols'][0]} [delete: {f['on_delete'].lower()}]")
        else:
            lc = ", ".join(f["cols"])
            pc = ", ".join(f["pcols"])
            out.append(f"Ref {f['name'][:60].replace('-', '_')}: {f['child']}.({lc}) > {f['parent']}.({pc}) [delete: {f['on_delete'].lower()}]")
    (erd / "scopus_ictu.dbml").write_text("\n".join(out) + "\n", encoding="utf8")


# ----------------------------------------------------------------------------- PlantUML class diagrams
CLS_HEAD = PUML_HEAD.replace("skinparam entity {{\n  BackgroundColor #FFFFFF\n  BorderColor #34495E\n  FontSize 12\n  AttributeFontSize 11\n}}\n",
                             "skinparam class {{\n  BackgroundColor #FFFFFF\n  BorderColor #34495E\n  FontSize 12\n  AttributeFontSize 11\n  HeaderBackgroundColor #ECF0F1\n}}\n") \
    .replace("hide circle\n", "hide circle\nhide empty methods\n")


def class_block(t, keys_only=False, stub=False):
    color = CLUSTER_COLOR[TABLE_CLUSTER[t]]
    if stub:
        return f'class "{t}" as {t} <<Table>> #EEEEEE {{\n  + {T[t]["pk"][0]} : uuid {{PK}}\n}}\n'
    pks, fkc = pk_set(t), fk_cols(t)
    lines = [f'class "{t}" as {t} <<Table>> {color} {{']
    for c in T[t]["columns"]:
        n = c["name"]
        if keys_only and n not in pks and n not in fkc:
            continue
        tags = []
        if n in pks:
            tags.append("PK")
        if n in fkc:
            tags.append("FK")
        if n in uq_cols(t):
            tags.append("UQ")
        tag = " {" + ", ".join(tags) + "}" if tags else ""
        null = "" if not c["nullable"] else "?"
        lines.append(f"  + {n}{null} : {short_type(c['type'])}{tag}")
    lines.append("}\n")
    return "\n".join(lines)


def assoc(f):
    """Quan hệ UML: CASCADE ⇒ composition (kim cương đặc ở phía cha); còn lại là association."""
    pm, cm = f["parent_mult"], f["child_mult"]
    arrow = "*--" if f["on_delete"] == "CASCADE" else "--"
    return f'{f["parent"]} "{pm}" {arrow} "{cm}" {f["child"]} : {", ".join(f["cols"])}'


def class_legend(keys_only):
    s = ("legend bottom right\n  <b>Chú giải UML</b>\n  Mỗi lớp «Table» = một bảng PostgreSQL; thuộc tính = cột; <i>?</i> = cho phép NULL\n"
         "  Kim cương đặc (composition) = khóa ngoại ON DELETE CASCADE; đường thường = ON DELETE RESTRICT\n"
         "  Bội số: phía bảng cha suy từ NOT NULL của cột FK; phía bảng con suy từ tính duy nhất của cột FK\n")
    if keys_only:
        s += "  <b>Hình rút gọn: chỉ hiển thị cột khóa (PK/FK); đầy đủ cột xem hình theo cụm</b>\n"
    return s + "endlegend\n"


def build_classes():
    cdir = DB / "class"

    def wr(name, body, title):
        txt = CLS_HEAD.format(name=name) + f"title {title}\n\n" + body + "\n@enduml\n"
        (cdir / f"{name}.puml").write_text(txt, encoding="utf8")

    body = ["left to right direction"]
    for k, c in CLUSTERS.items():
        body.append(f'package "Cụm {k} – {c["name"]}" {CLUSTER_COLOR[k]} {{')
        for t in c["tables"]:
            body.append(class_block(t, keys_only=True))
        body.append("}")
    body += [assoc(f) for f in FKS]
    body.append(class_legend(True))
    wr("CLS-0_tong_the_cot_khoa", "\n".join(body), "CLS-0 — Sơ đồ lớp tổng thể (cột khóa) của 24 bảng")
    for k, c in CLUSTERS.items():
        tabs = set(c["tables"])
        stubs, rels = set(), []
        for f in FKS:
            if f["child"] in tabs or f["parent"] in tabs:
                rels.append(f)
                stubs |= {x for x in (f["child"], f["parent"]) if x not in tabs}
        body = [class_block(t) for t in c["tables"]] + [class_block(s, stub=True) for s in sorted(stubs)]
        body += [assoc(f) for f in rels]
        body.append(class_legend(False))
        wr(f"CLS-{CLUSTER_SLUG[k]}", "\n".join(body), f"CLS-{k} — Sơ đồ lớp cụm {k}: {c['name']}")


def main():
    for d in (DB / "erd", DB / "class"):
        d.mkdir(parents=True, exist_ok=True)
    build_dictionary()
    build_keys()
    build_checks()
    build_erds()
    build_classes()
    print("OK:", len(T), "bảng;", len(FKS), "FK")


if __name__ == "__main__":
    main()
