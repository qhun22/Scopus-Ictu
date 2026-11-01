# E3-P1 final closeout — handover for owner review

Date: 2026-10-29 · Status: **ALL KNOWN E3-P1 DEFECTS CLOSED — READY FOR OWNER REVIEW**

This pass closes OPEN-1..4 from `E3P1_ERRATA_HANDOVER.md` and the R1 URL findings from the
independent errata review. No strict-xfail remains. The architecture is unchanged, and so is the output
for valid input: P1, errata and closeout produce an identical digest of all hashes, keys, normalized values,
issues and claims.

## 1. Result

| Check | Result |
|---|---|
| E3-P1 pure suite (`--noconftest`) | **118 passed, 0 xfailed, 0 skipped, 0 failed** |
| Ruff (`app/services/source_claims`, `tests/unit/test_source_claims.py`) | **exit 0** |
| Parser ⇔ JSON Schema parity (real `jsonschema` 4.26.0 Draft 2020-12 validator) | identical accept/reject on 24 versions, both on the field and on the whole artifact |
| Replay P1 → errata → closeout diffs on an empty Git tree (`--whitespace=error`) | 7/7 files reproduce the workspace byte for byte; reverse check OK |
| Scoped whitespace check (`git diff --no-index --check`) | clean (closeout and cumulative) |
| Cross-process determinism (PYTHONHASHSEED 0 / 1 / 4242 / random) | one digest |
| Purity: forbidden modules newly imported by `source_claims` | `[]` with `-I -S` and with `-I`; preloaded: `[]` |
| G01–G04: 31 recorded files re-hashed against the latest gate record | 31/31 MATCH |
| `git status` tracked-modified set | identical to the session start (15 files) |

## 2. Changes (closeout diff relative to P1 + errata)

| File | +/− | Purpose |
|---|---|---|
| `backend/app/services/source_claims/parser.py` | +26 / −15 | OPEN-1, OPEN-2, OPEN-3, OPEN-4 |
| `backend/app/services/source_claims/canonical.py` | +13 / −8 | R1 completion |
| `data/source_claims/schema/ictu_source_claims.schema.json` | +1 / −1 | OPEN-3 (schema side) |
| `backend/tests/unit/test_source_claims.py` | +153 / −42 | xfails → regressions; new tests; purity delta |

`contract.py`, `analysis.py` and `__init__.py` are unchanged since P1.

**OPEN-1 (`|=` mutation).** `_FrozenMap.__ior__` now raises `TypeError`. The non-mutating `mapping | {...}`
still returns a new plain `dict`. Read access, equality, `copy`, `deepcopy` and `json.dumps` are unchanged,
and a test covers each of them.

**OPEN-2 (pickle).** `_FrozenMap.__reduce__` returns `(_frozen_map, (dict(self),))`. Pickle therefore
rebuilds the object through the same bypassing constructor, never through `__setitem__`. A snapshot
round-trips under protocols 2 to 5. Content and record hashes are equal, deepcopy still works, and every
rebuilt mapping still rejects `[]=`, `update` and `|=`. This only concerns snapshots that the application
creates itself: **never unpickle untrusted data**.

**OPEN-3 (strict version).**
- Parser: `re.fullmatch(rf"{CONTRACT_MAJOR}\.[0-9]+", version)`. The string must be a `str`, with ASCII
  digits only and nothing before or after.
- Schema: the pattern is now `^1\.[0-9]+(?![\s\S])`. The lookahead is valid in ECMA-262 and in Python
  `re`. It replaces `$`, which `jsonschema` matches before a final newline. With the old pattern the real
  validator accepts `"1.0\n"`; with the new one it rejects it (log §6).
- Accepted: `1.0`, `1.1`, `1.99`, `1.00`, `1.10`.
- Rejected:
  - malformed formats: `01.0`, `001.5`, `1.0\n`, `1.0\r`, `1.0\r\n`, `1.0.1`, `1`, `1.`, `.1`, `1.x`, `1.-1`
  - surrounding whitespace: ` 1.0`, `1.0 `, `\n1.0`
  - unsupported majors: `2.0`, `0.9`, `10.0`
  - Arabic-Indic digits: `1.١`, `١.0`
- Non-string values are rejected too: integers, `None` and lists raise `UNSUPPORTED_CONTRACT_VERSION`; floats
  are rejected earlier as `NON_CANONICAL_VALUE`.

**OPEN-4 (Ruff).** The three quoted annotations are removed (`from __future__ import annotations` already
applies).

**R1 completion (URL safety).**
- A URL with no host returns `normalized=None` with an ERROR `SOURCE_URL_MALFORMED`. Examples:
  `https:///profile/123`, `https://`, `http://:80/`, `http://?q=1`, `http://#frag`.
- In such a row, the raw value is kept and the key falls back to e-mail (MEDIUM) or content (WEAK). It is
  never STRONG.
- At artifact level, a `content.source_url` with no host raises `ArtifactError("SOURCE_URL_MALFORMED")`.
- An IPv6 host keeps its brackets, and a non-default port is kept:
  - `http://[::1]:8080/a/` → `http://[::1]:8080/a`
  - `https://[2001:DB8::1]:443/x` → `https://[2001:db8::1]/x`
- Hostname and IPv4 normalization and default-port removal are unchanged. Every normalized URL parses
  back to the same host and port, and normalizing it again gives the same value (test-checked).
- No other URL rule was changed.

**Purity test.** It now records `sys.modules` before the import and reports two lists:
- `preloaded`: forbidden modules the interpreter or site configuration had already loaded;
- `new`: forbidden modules loaded by importing `source_claims.parser` and `.analysis`.

Only `new` must be empty. The test runs twice: with `-I -S` (no site, so no preload, which also catches
a forbidden import that a preload could hide) and with `-I`. This resolves the reviewer's container
failure without weakening the production purity boundary.

## 3. Remaining limitations (none blocks P1)

1. `jsonschema` is installed here (4.26.0) but is **not** a declared dev dependency. `pyproject.toml` is
   outside this scope. The parity test uses `pytest.importorskip`, so where jsonschema is missing it
   *skips* instead of failing. Recommendation: add `jsonschema` to `[project.optional-dependencies].dev`
   when P2 opens.
2. Pickle support is only for trusted, application-produced snapshots. P2 should still prefer the JSON
   forms (`raw_json`, `content_json`, `canonical_json`) for persistence.
3. Calling `dict.__setitem__(mapping, …)` directly on the base class bypasses any Python-level guard.
   Python cannot prevent this; it is deliberate misuse, not an accidental mutation path.
4. URL normalization still drops user info (`user:pw@`) and keeps IPv6 zone IDs (`%25eth0`) as given.
   Both are P1 behavior that this narrow scope left unchanged.
5. The tests ran with `--noconftest`, because the project conftest requires an allowlisted PostgreSQL test
   DB. No database was used. G04 PostgreSQL acceptance remains a separate condition before any real ICTU
   import.

## 4. Scope

Modified: `canonical.py`, `parser.py`, the source-claims JSON Schema, `test_source_claims.py`, and these
closeout documents. Nothing else changed: no DB, model, migration, API, frontend, real import, G01–G04
file, commit or push. E3-P2 has not started.

## 5. Artifacts

- `E3P1_CLOSEOUT_IMPLEMENTATION.diff`: closeout diff relative to P1 + errata, rebuilt from the two
  delivered diffs. It is not a Git HEAD diff, because `source_claims/` is untracked. Apply it after
  `E3P1_IMPLEMENTATION.diff` and `E3P1_ERRATA_IMPLEMENTATION.diff`.
- `E3P1_CLOSEOUT_TEST_RESULTS.txt`: every command and log behind §1.
- `E3P1_CLOSEOUT_VALIDATION.json`: hashes of the final files and artifacts, plus all measured results.
