# E3-P1 narrow errata — handover for independent acceptance

Date: 2026-10-29 · Scope: P1-R1, P1-R2, P1-R3 only · Status: **ERRATA DELIVERED, NOT READY TO CLOSE P1**

While preparing this handover I re-probed my own errata the way the reviewer asked. The three original
reproductions are fixed. But the same probe found **four open gaps in the errata itself** (OPEN-1..4
below). This step forbids code changes, so they are not fixed. Each is reproduced by a `strict` xfail
test or by Ruff output. A second narrow pass (estimated under 15 changed production lines) is needed
before P1 can close.

## 1. Baseline and diff

- The baseline is E3-P1 as delivered. I applied `E3P1_IMPLEMENTATION.diff` to an empty Git tree
  (`core.autocrlf=false`). All 7 files re-hash to the values in `E3P1_VALIDATION.json`.
- `E3P1_ERRATA_IMPLEMENTATION.diff` compares that baseline with the current workspace. It is not a Git
  HEAD diff, because `source_claims/` is untracked.
- Replay on an empty tree: apply the P1 diff, then the errata diff with `--whitespace=error`. All 3 changed
  files reproduce the current workspace byte for byte, and `git apply -R --check` succeeds.

| File | Change | +/- lines | Errata SHA-256 |
|---|---|---|---|
| `backend/app/services/source_claims/canonical.py` | R1 | +19 / −8 | `887a5445…d266c` |
| `backend/app/services/source_claims/parser.py` | R1, R2, R3 | +59 / −3 | `f92f72a2…08049` |
| `backend/tests/unit/test_source_claims.py` | tests, fixture fix | +197 / −3 | `f3b2f425…04120` |
| `contract.py`, `analysis.py`, `__init__.py`, schema JSON | unchanged | 0 | equal to P1 |

The full hashes are in `E3P1_ERRATA_VALIDATION.json`.

## 2. What changed

**R1: a malformed URL no longer crashes parsing** (`canonical.py` `normalize_source_id`, `parser.py` `parse_artifact`)
- URL normalization is wrapped in `try/except ValueError`. A malformed `http(s)` URL now returns
  `normalized=None` with an ERROR issue `SOURCE_URL_MALFORMED`, and the raw value is kept.
- The profile key then falls back by the existing rules: source_id → e-mail (MEDIUM) → content (WEAK).
  A malformed URL is never a STRONG key.
- At artifact level, a `content.source_url` that cannot be normalized raises
  `ArtifactError("SOURCE_URL_MALFORMED")`. The normalized value is computed once and reused for `scope_key`.

**R2: stored normalized evidence is immutable** (`parser.py` `_FrozenMap`, `_normalized_pairs`)
- Each `SourceRecord.normalized` entry is now a `_FrozenMap`, a `dict` subclass. `__setitem__`,
  `__delitem__`, `update`, `pop`, `popitem`, `clear` and `setdefault` all raise `TypeError`.
- `__deepcopy__` and `__copy__` are explicit. Equality, `dict(...)`, `json.dumps` and read access behave
  like a normal dict.
- Leaf values are only `str` or `None`; this is checked by a test. There is no nested list or dict to
  mutate. The reviewer's example `record.normalized["author"]["name"] = ...` raises `TypeError`, because
  `normalized` is a tuple of `(name, mapping)` pairs and is indexed by integer, not by field name.
- `raw_json`, `record_hash`, the claims and every hash rule are unchanged.

**R3: the contract version follows a grammar** (`parser.py` `_CONTRACT_VERSION_RE`)
- The rule is the regex `^([0-9]+)\.[0-9]+$` plus `int(major) == CONTRACT_MAJOR`.
- The major check is real. `2.0`, `0.9` and `10.0` are rejected with `UNSUPPORTED_CONTRACT_VERSION`.
  `1.x`, `1.0.1`, `1` and `1.` are also rejected.
- The alignment is **not complete**; see OPEN-3.

**Test fixture (pre-existing P1 test bug).** `guide()` stored references to the module-level
`ID_COLUMNS`/`MULTI_COLUMNS` lists. `test_envelope_violations_raise` mutated them with `.pop(1)` and
`.update(role="EMAIL")`, which corrupted every later `base_guide()` call. Each call now builds its own
column dicts. This is test-only and changes no assertion in an existing test.

## 3. Evidence the reviewer asked for

| Request | Test | Result |
|---|---|---|
| Nested normalized data cannot be mutated | `test_errata_nested_normalized_access_cannot_mutate_stored_evidence` (7 mutators, string indexing, leaf types, deepcopy equality) | PASS |
| Version 2.0 is rejected | `test_errata_major_version_2_is_rejected`, `test_r3_invalid_contract_versions_are_rejected[2.0]` | PASS |
| A bad URL does not lose the record | `test_errata_malformed_url_keeps_record_raw_and_claims` (record kept, `raw` equal to the input, INVALID, non-STRONG key, e-mail and ORCID claims kept) and `test_r1_*` (invalid port, malformed IPv6, artifact-level error, valid URL still normalizes) | PASS |

Suite: **80 passed, 5 xfailed** (85 collected; P1 had 58). The 5 xfails are the strict reproductions of
OPEN-1..3. Command and log: `E3P1_ERRATA_TEST_RESULTS.txt`.

## 4. Open gaps in the errata (found here, not fixed)

| ID | Gap | Reproduction | Smallest fix (not applied) |
|---|---|---|---|
| OPEN-1 | `mapping \|= {...}` **mutates** a `_FrozenMap`, because `dict.__ior__` does not call the overridden `update`. R2 is therefore incomplete. | `test_open_1_inplace_or_must_not_mutate_normalized` (strict xfail) | Override `__ior__` to raise `TypeError` |
| OPEN-2 | `pickle.loads(pickle.dumps(snapshot))` raises `TypeError`, because pickle rebuilds dict subclasses through `__setitem__`. Any serialization to a worker or cache in P2 would break. | `test_open_2_snapshot_survives_pickle_roundtrip` (strict xfail) | `__reduce__` returning `(_FrozenMap._make, (dict(self),))` |
| OPEN-3 | The parser accepts `01.0`, `001.5` and `"1.0\n"`; the schema `^1\.[0-9]+$` rejects all three. The causes are leading zeros in the major part and Python's `$` matching before a trailing newline. | `test_open_3_…[01.0/001.5/1.0\n]` (strict xfail) | `re.fullmatch(rf"{CONTRACT_MAJOR}\.[0-9]+", version, re.ASCII)` |
| OPEN-4 | Ruff: 3 × UP037 (quoted return annotations in `_FrozenMap`). P1 was Ruff-clean. | `E3P1_ERRATA_TEST_RESULTS.txt` §4 | `ruff check --fix --select UP037` |

When a gap is closed, its strict xfail turns into a hard failure. The `xfail` marker must then be removed,
so a fixed gap cannot go unnoticed.

Accepted residual (not a defect): `dict.__setitem__(mapping, k, v)` called directly on the base class
bypasses any Python-level guard. Python cannot prevent this. It is deliberate misuse, not an accidental
mutation path.

## 5. Scope and preservation

- Production files changed: `canonical.py` and `parser.py` only. `source_claims` imports stdlib only; I
  added `re` and `copy`. The purity test (`python -I` subprocess, with no sqlalchemy, fastapi, requests,
  socket, etc.) passes and was not weakened.
- G04: its 4 files and 2 artifacts re-hash to `G04_VALIDATION.json`, all MATCH. G01–G03 files were not
  touched (no edit outside `source_claims/`, its test file and these 4 docs).
- `git status --short` is identical to the session-start snapshot (same 15 tracked modified files). The
  only additions are these 4 untracked files.
- No model, migration, database, API, frontend, real import, commit or push. E3-P2 has not started.
- Environment note: `tests/conftest.py` exits without an allowlisted `TEST_DATABASE_URL`, so the pure
  file was run with `--noconftest`. No database was configured.

## 6. Correction history

1. Fixed R1, R2 (first with `types.MappingProxyType`) and R3, and added 19 regression tests.
2. `MappingProxyType` broke `copy.deepcopy` of a snapshot (an existing P1 test failed), so I replaced it
   with the `_FrozenMap` dict subclass and explicit `__deepcopy__`.
3. The new R3 tests failed because of a shared mutable fixture, first through `.pop(1)` and then through
   the inner dict's `.update(role=...)`. A shallow copy was not enough, so the fixture now copies each
   column dict. Result: 77/77.
4. Handover probe, this step: the reviewer's two concerns were valid. The probe found OPEN-1..4. I added
   evidence tests and strict-xfail reproductions, test code only, and fixed one E501 in the test file. Result:
   80 passed, 5 xfailed.

**Recommended decision:** do not close P1 yet. Authorize one more narrow pass for OPEN-1..4 only. It
touches only `_FrozenMap` and the version check, and turns the 5 xfails into passing tests. After that,
P1 can close and E3-P2 can start.
