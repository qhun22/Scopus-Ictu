"""Trích lược đồ PostgreSQL ra JSON (CHỈ ĐỌC).

Cách dùng:
    python -I -X utf8 extract_schema.py --env-file <tệp .env của backend> --out ../database/source/schema_snapshot.json

* Kết nối bằng `psycopg2`, đặt phiên `READ ONLY` (set_session(readonly=True)); chỉ chạy SELECT trên
  `pg_catalog` / `information_schema` và `SELECT count(*)`.
* Không in mật khẩu; tệp .env chỉ được đọc để lấy thông số kết nối.
* Từ chối kết nối tới cổng 5432 (dịch vụ PostgreSQL của Windows, không thuộc dự án).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

import psycopg2


def load_env(path: str) -> dict[str, str]:
    env: dict[str, str] = {}
    with open(path, encoding="utf8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"')
    return env


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--db", help="ghi đè tên DB (mặc định lấy từ env-file)")
    args = ap.parse_args()
    env = load_env(args.env_file)
    if str(env["DB_PORT"]) == "5432":
        print("TỪ CHỐI: không dùng PostgreSQL cổng 5432", file=sys.stderr)
        return 2
    dbname = args.db or env["DB_NAME"]
    conn = psycopg2.connect(host=env["DB_HOST"], port=env["DB_PORT"], dbname=dbname,
                            user=env["DB_USER"], password=env["DB_PASSWORD"], connect_timeout=8)
    conn.set_session(readonly=True, autocommit=False)
    cur = conn.cursor()
    cur.execute("show transaction_read_only")
    assert cur.fetchone()[0] == "on", "phiên phải ở chế độ chỉ đọc"
    cur.execute("select current_database(), split_part(version(), ' ', 2)")
    cur_db, pg_version = cur.fetchone()
    cur.execute("select version_num from alembic_version")
    alembic = [r[0] for r in cur.fetchall()]

    cur.execute("""select c.relname, obj_description(c.oid)
                   from pg_class c join pg_namespace n on n.oid=c.relnamespace
                   where n.nspname='public' and c.relkind='r' and c.relname <> 'alembic_version' order by 1""")
    tables = {r[0]: {"comment": r[1]} for r in cur.fetchall()}

    for t, info in tables.items():
        cur.execute("""select a.attname, format_type(a.atttypid, a.atttypmod), not a.attnotnull,
                              pg_get_expr(d.adbin, d.adrelid), a.attnum
                       from pg_attribute a
                       left join pg_attrdef d on d.adrelid=a.attrelid and d.adnum=a.attnum
                       where a.attrelid=('public.'||%s)::regclass and a.attnum>0 and not a.attisdropped
                       order by a.attnum""", (t,))
        info["columns"] = [dict(name=r[0], type=r[1], nullable=r[2], default=r[3], pos=r[4]) for r in cur.fetchall()]

        def names(oid_array_sql, params):
            cur.execute(oid_array_sql, params)
            return cur.fetchall()

        cur.execute("""select con.conname, con.contype, pg_get_constraintdef(con.oid),
                              (select array_agg(a.attname order by k.ord) from unnest(con.conkey) with ordinality k(attnum, ord)
                               join pg_attribute a on a.attrelid=con.conrelid and a.attnum=k.attnum),
                              ref.relname,
                              (select array_agg(a.attname order by k.ord) from unnest(con.confkey) with ordinality k(attnum, ord)
                               join pg_attribute a on a.attrelid=con.confrelid and a.attnum=k.attnum),
                              con.confdeltype, con.confupdtype
                       from pg_constraint con left join pg_class ref on ref.oid=con.confrelid
                       where con.conrelid=('public.'||%s)::regclass order by con.contype, con.conname""", (t,))
        pk, fks, uqs, cks = [], [], [], []
        dmap = {"a": "NO ACTION", "r": "RESTRICT", "c": "CASCADE", "n": "SET NULL", "d": "SET DEFAULT"}
        for name, ctype, expr, cols, ref, refcols, deltype, updtype in cur.fetchall():
            if ctype == "p":
                pk = list(cols)
            elif ctype == "f":
                fks.append(dict(name=name, cols=list(cols), ref_table=ref, ref_cols=list(refcols),
                                on_delete=dmap[deltype], on_update=dmap[updtype]))
            elif ctype == "u":
                uqs.append(dict(name=name, cols=list(cols)))
            elif ctype == "c":
                cks.append(dict(name=name, expr=expr))
        info.update(pk=pk, fks=fks, uniques=uqs, checks=cks)

        cur.execute("""select i.relname, ix.indisunique, ix.indisprimary, pg_get_indexdef(ix.indexrelid),
                              pg_get_expr(ix.indpred, ix.indrelid), am.amname,
                              exists(select 1 from pg_constraint c where c.conindid=ix.indexrelid)
                       from pg_index ix join pg_class i on i.oid=ix.indexrelid join pg_am am on am.oid=i.relam
                       where ix.indrelid=('public.'||%s)::regclass order by i.relname""", (t,))
        info["indexes"] = [dict(name=r[0], unique=r[1], primary=r[2], definition=r[3], predicate=r[4], method=r[5],
                                backs_constraint=r[6]) for r in cur.fetchall()]
        cur.execute(f'select count(*) from "{t}"')
        info["row_count"] = cur.fetchone()[0]

    cur.execute("select count(*) from pg_trigger where not tgisinternal")
    triggers = cur.fetchone()[0]
    cur.execute("""select count(*) from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public'""")
    functions = cur.fetchone()[0]
    cur.execute("select extname from pg_extension order by 1")
    extensions = [r[0] for r in cur.fetchall()]
    conn.rollback()
    conn.close()

    snapshot = dict(
        meta=dict(extracted_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), database=cur_db,
                  postgres_version=pg_version, alembic_version=alembic, triggers=triggers, functions=functions,
                  extensions=extensions, mode="READ ONLY (set_session readonly=True)"),
        tables=tables)
    with open(args.out, "w", encoding="utf8") as fh:
        json.dump(snapshot, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"OK: {len(tables)} bảng; DB={cur_db}; alembic={alembic}; trigger={triggers}; hàm={functions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
