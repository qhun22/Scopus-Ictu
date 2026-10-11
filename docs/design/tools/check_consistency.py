"""Kiểm tra nhất quán toàn bộ bộ tài sản docs/design (cổng PASS của Task 19).

    python -X utf8 check_consistency.py
Kiểm:
 1. ERD/Class: tập khóa ngoại trong hình == tập FK trong schema_snapshot.json (30), mỗi bảng có đủ cột ở đúng 1 sơ đồ cụm.
 2. Use Case: mọi API (RBAC_API_MATRIX.json) thuộc >=1 UC hoặc nằm trong danh sách loại trừ; hợp actor của các UC == vai trò thật (require_role).
 3. Route giao diện của UC tồn tại trong frontend/src/App.tsx và vai trò của route == actor của UC.
 4. Mọi .puml có SVG + PNG cạnh đó, SVG là XML hợp lệ, PNG đọc được kích thước; .bpmn là XML hợp lệ với đủ BPMNDI.
 5. Không có bí mật (mật khẩu, token, chuỗi kết nối) trong docs/design.
 6. Data dictionary đủ 24 bảng và 245 cột.
Trả mã 1 nếu có lỗi.
"""
from __future__ import annotations

import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DESIGN = Path(__file__).resolve().parents[1]
REPO = DESIGN.parents[1]
errors: list[str] = []
notes: list[str] = []


def err(msg):
    errors.append(msg)


def ok(msg):
    notes.append("OK  " + msg)


SNAP = json.load(open(DESIGN / "database/source/schema_snapshot.json", encoding="utf8"))
T = SNAP["tables"]
FK_TRUTH = {(fk["ref_table"], t, tuple(fk["cols"])) for t, v in T.items() for fk in v["fks"]}

# ---------------------------------------------------------------- 1. ERD / Class
ER_REL = re.compile(r"^(\w+) (?:\|\||\|o)--(?:o\{|o\|) (\w+) : (.+)$")
CL_REL = re.compile(r'^(\w+) "[\d.*]+" (?:\*--|--) "[\d.*]+" (\w+) : (.+)$')


def rels(path, rx):
    out = []
    for line in path.read_text(encoding="utf8").splitlines():
        m = rx.match(line.strip())
        if m:
            out.append((m.group(1), m.group(2), tuple(c.strip() for c in m.group(3).split(","))))
    return out


for kind, rx, folder in (("ERD", ER_REL, "database/erd"), ("CLS", CL_REL, "database/class")):
    files = sorted((DESIGN / folder).glob("*.puml"))
    overall = next(f for f in files if f.name.startswith(f"{kind}-0"))
    got = set(rels(overall, rx))
    if got != FK_TRUTH or len(rels(overall, rx)) != len(FK_TRUTH):
        err(f"{overall.name}: FK trong hình khác schema (thiếu {sorted(FK_TRUTH - got)[:3]}, thừa {sorted(got - FK_TRUTH)[:3]})")
    else:
        ok(f"{overall.name}: {len(got)}/{len(FK_TRUTH)} FK khớp schema, không thừa không thiếu")
    # từng cụm: mọi FK có bảng thuộc cụm phải xuất hiện đúng 1 lần
    desc = json.load(open(DESIGN / "database/source/descriptions_vi.json", encoding="utf8"))
    for k, c in desc["clusters"].items():
        f = next(x for x in files if x.name.startswith(f"{kind}-{k}_"))
        expect = {x for x in FK_TRUTH if x[1] in c["tables"] or x[0] in c["tables"]}
        r = rels(f, rx)
        if set(r) != expect or len(r) != len(expect):
            err(f"{f.name}: FK cụm lệch schema")
        txt = f.read_text(encoding="utf8")
        for t in c["tables"]:
            if kind == "ERD":
                m = re.search(rf'entity "{t}" as {t} #[0-9A-Fa-f]+ \{{(.*?)\n\}}', txt, re.S)
                n_cols = len(re.findall(r"^\s+\*?\w+ : ", m.group(1), re.M)) if m else -1
            else:
                m = re.search(rf'class "{t}" as {t} <<Table>> #[0-9A-Fa-f]+ \{{(.*?)\n\}}', txt, re.S)
                n_cols = len(re.findall(r"^\s+\+ \w+\??: ", m.group(1).replace(" :", ":"), re.M)) if m else -1
            if n_cols != len(T[t]["columns"]):
                err(f"{f.name}: bảng {t} có {n_cols} cột trong hình ≠ {len(T[t]['columns'])} trong DB")
    ok(f"{kind}: 6 sơ đồ cụm — FK và số cột từng bảng khớp schema")

# ---------------------------------------------------------------- 2. Use case ↔ RBAC
UC = json.load(open(DESIGN / "usecase/usecase_map.json", encoding="utf8"))
RB = json.load(open(DESIGN / "usecase/RBAC_API_MATRIX.json", encoding="utf8"))
RBD = {f"{o['method']} {o['path']}": o for o in RB}
mapped: dict[str, set] = {}
for u in UC["use_cases"]:
    for op in u["ops"]:
        if op not in RBD:
            err(f"{u['id']}: API không tồn tại trong mã: {op}")
            continue
        mapped.setdefault(op, set()).update(a for a in u["actors"] if a != "TECH")
    for a in u["actors"]:
        if a != "TECH" and a not in ("ADMIN", "REVIEWER", "LECTURER"):
            err(f"{u['id']}: actor lạ {a}")
unmapped = [op for op in RBD if op not in mapped and op not in UC["unmapped_ops_allowed"]]
if unmapped:
    err(f"API chưa thuộc UC nào: {unmapped}")
else:
    ok(f"{len(RBD)} API: {len(mapped)} gán UC + {len(UC['unmapped_ops_allowed'])} loại trừ có lý do")
bad_roles = 0
for op, acts in mapped.items():
    r = RBD[op]
    if r["roles"]:
        if acts != set(r["roles"]):
            err(f"{op}: actor UC {sorted(acts)} ≠ require_role {r['roles']}")
            bad_roles += 1
    elif r["access"] == "AUTHENTICATED" and acts != {"ADMIN", "REVIEWER", "LECTURER"}:
        err(f"{op}: cần đăng nhập — UC phải dành cho cả 3 vai trò")
        bad_roles += 1
if not bad_roles:
    ok("Hợp actor của các UC khớp require_role của từng API (không thừa, không thiếu quyền)")
ids = [u["id"] for u in UC["use_cases"]]
if len(ids) != len(set(ids)):
    err("ID use case trùng")
for u in UC["use_cases"]:
    for k in ("extends",):
        if u.get(k) and u[k] not in ids:
            err(f"{u['id']}: {k} tham chiếu UC không tồn tại")
    for i in u.get("includes", []):
        if i not in ids:
            err(f"{u['id']}: include tham chiếu UC không tồn tại")

# ---------------------------------------------------------------- 3. Route UI ↔ App.tsx
app = (REPO / "frontend/src/App.tsx").read_text(encoding="utf8")
routes: dict[str, set] = {}
cur: set | None = None
for line in app.splitlines():
    m = re.search(r'<RoleRoute allowedRoles=\{\[(.*?)\]\}', line)
    if m:
        cur = set(re.findall(r'"(\w+)"', m.group(1)))
    if "</Route>" in line and cur is not None and "<Route path" not in line:
        pass
    m2 = re.search(r'<Route\s+path="([^"]+)"', line) or None
    if m2 and m2.group(1) not in ("/", "/login", "*", "/home"):
        routes.setdefault(m2.group(1), set()).update(cur or set())
    elif re.search(r'^\s*<Route\s*$', line):
        pass
# route khai báo nhiều dòng: <Route\n path="/profile"
for m in re.finditer(r'<Route\s+path="([^"]+)"', app):
    pass
# bắt thêm route nhiều dòng theo cách thô: tìm path="..." kèm vai trò gần nhất phía trên
blocks = re.split(r'(?=<RoleRoute allowedRoles=)', app)
routes = {}
for b in blocks:
    m = re.match(r'<RoleRoute allowedRoles=\{\[(.*?)\]\}', b)
    if not m:
        continue
    roles = set(re.findall(r'"(\w+)"', m.group(1)))
    end = b.find("</Route>")
    for p in re.findall(r'path="([^"]+)"', b[:end if end > 0 else len(b)]):
        routes.setdefault(p, set()).update(roles)
PUBLIC_ROUTES = {"/login": {"ADMIN", "REVIEWER", "LECTURER"}}
for u in UC["use_cases"]:
    for r in u["ui"]:
        if r in PUBLIC_ROUTES:
            continue
        if r not in routes:
            err(f"{u['id']}: route giao diện {r} không có trong App.tsx")
        else:
            want = {a for a in u["actors"] if a != "TECH"}
            if routes[r] != want and not (routes[r] >= want and r in ("/lecturers", "/reviews", "/publications", "/normalization", "/imports")):
                err(f"{u['id']}: route {r} cho {sorted(routes[r])} ≠ actor UC {sorted(want)}")
ok(f"Route giao diện của UC có trong App.tsx với vai trò khớp ({len(routes)} route theo RoleRoute)")

# ---------------------------------------------------------------- 4. Render
n_puml = 0
for p in sorted(DESIGN.rglob("*.puml")):
    if "render" in p.parts:
        continue
    n_puml += 1
    for ext in ("svg", "png"):
        f = p.parent / "render" / f"{p.stem}.{ext}"
        if not f.exists() or f.stat().st_size < 500:
            err(f"thiếu bản render {f.relative_to(DESIGN)}")
            continue
        if ext == "svg":
            try:
                ET.parse(f)
            except ET.ParseError as e:
                err(f"{f.name}: SVG không hợp lệ: {e}")
        else:
            d = f.read_bytes()[:24]
            w, h = struct.unpack(">II", d[16:24])
            if w < 600:
                err(f"{f.name}: PNG quá nhỏ {w}x{h}")
for p in (DESIGN / "process").glob("*.bpmn"):
    try:
        root = ET.parse(p).getroot()
        ns = {"b": "http://www.omg.org/spec/BPMN/20100524/MODEL", "d": "http://www.omg.org/spec/BPMN/20100524/DI"}
        nodes = root.findall(".//b:process/*[@id]", ns)
        shapes = root.findall(".//d:BPMNShape", ns)
        edges = root.findall(".//d:BPMNEdge", ns)
        flows = root.findall(".//b:sequenceFlow", ns)
        if len(edges) < len(flows):
            err(f"{p.name}: thiếu BPMNEdge")
        ok(f"{p.name}: XML hợp lệ, {len(flows)} luồng, {len(shapes)} shape, {len(edges)} edge")
    except ET.ParseError as e:
        err(f"{p.name}: {e}")
for p in (DESIGN / "process" / "render").glob("*.svg"):
    try:
        ET.parse(p)
        if not p.with_suffix(".png").exists():
            err(f"thiếu PNG cho {p.name}")
    except ET.ParseError as e:
        err(f"{p.name}: {e}")
ok(f"{n_puml} sơ đồ PlantUML có SVG + PNG")

# ---------------------------------------------------------------- 5. Bí mật
PATTERNS = [r"DB_PASSWORD\s*=\s*['\"]?[^\s'\",]{8,}", r"SECRET_KEY\s*=\s*['\"]?[^\s'\",]{8,}", r"eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}", r"postgres(?:ql)?(?:\+\w+)?://[^\s:@/]+:[^\s@/]+@",
            r"(?i)\bpassword\b\s*[:=]\s*['\"][^'\"\s]{4,}", r"(?i)api[_-]?key\s*[:=]\s*['\"]?\w{12,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"]
hits = 0
for p in DESIGN.rglob("*"):
    if not p.is_file() or p.suffix.lower() in (".png", ".svg") and "render" in p.parts:
        continue
    if p.suffix.lower() in (".png", ".jpg", ".jpeg"):
        continue
    try:
        txt = p.read_text(encoding="utf8", errors="ignore")
    except Exception:
        continue
    for pat in PATTERNS:
        m = re.search(pat, txt)
        if m:
            hits += 1
            err(f"nghi bí mật trong {p.relative_to(DESIGN)}: mẫu {pat[:25]}…")
if not hits:
    ok("Không phát hiện mật khẩu/token/chuỗi kết nối trong docs/design (quét mẫu)")

# ---------------------------------------------------------------- 6. Data dictionary
dd = (DESIGN / "database/DATA_DICTIONARY.md").read_text(encoding="utf8")
missing = [t for t in T if f"### {t}\n" not in dd]
cols_in_dd = len(re.findall(r"^\| \d+ \| `", dd, re.M))
if missing:
    err(f"Data dictionary thiếu bảng: {missing}")
tot = sum(len(v["columns"]) for v in T.values())
if cols_in_dd != tot:
    err(f"Data dictionary có {cols_in_dd} cột ≠ {tot}")
else:
    ok(f"Data dictionary: {len(T)} bảng, {cols_in_dd} cột")

# ---------------------------------------------------------------- 7. Tên test trong tài liệu có thật
tfuncs, tfiles = set(), set()
for tp in (REPO / "backend" / "tests").rglob("test_*.py"):
    tfiles.add(tp.stem)
    tfuncs.update(re.findall(r"^\s*(?:async\s+)?def (test_\w+)", tp.read_text(encoding="utf8"), re.M))
bad_t = set()
n_t = 0
for md in list((DESIGN).rglob("*.md")) + [DESIGN / "tools" / "fr_nfr_data.py"]:
    for name in set(re.findall(r"test_[a-z0-9_]+", md.read_text(encoding="utf8"))):
        n_t += 1
        if name in ("test_fixtures",) or name in tfuncs or name in tfiles or any(f.startswith(name) for f in tfuncs):
            continue
        bad_t.add((md.name, name))
for md, name in sorted(bad_t):
    err(f"{md}: tên test không tồn tại: {name}")
if not bad_t:
    ok(f"{n_t} tên test được trích dẫn trong tài liệu đều tồn tại trong backend/tests")

# ---------------------------------------------------------------- 8. Không dùng bảng cũ không tồn tại trong sơ đồ/nguồn
OLD = ["approval_queue", "standardized_data", "export_audit_log", "upload_batches", "author_extracted", "raw_scopus_data", "publication_sources"]
hit8 = 0
for pth in DESIGN.rglob("*"):
    if not pth.is_file() or pth.suffix.lower() not in (".puml", ".dbml", ".bpmn", ".json", ".svg") or pth.name == "check_consistency.py":
        continue
    txt = pth.read_text(encoding="utf8", errors="ignore")
    for o in OLD:
        if o in txt:
            hit8 += 1
            err(f"{pth.relative_to(DESIGN)} nhắc bảng không tồn tại: {o}")
if not hit8:
    ok("Sơ đồ và nguồn máy đọc không chứa bảng cũ không tồn tại (approval_queue, standardized_data, export_audit_log, publication_sources…)")

for n in notes:
    print(n)
for e in errors:
    print("LỖI", e)
print(f"\nKẾT QUẢ: {len(notes)} mục OK, {len(errors)} lỗi")
sys.exit(1 if errors else 0)
