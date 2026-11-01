# E3-P2-B1 provenance correction (B1-R1, B1-R2): handover for independent review

Date: 2026-10-29 · Status: **CORRECTION DELIVERED — STOPPED FOR REVIEW** (B2 not started)

Scope: `backend/app/services/source_claims/provenance.py` and its test file only. The following are
unchanged, all hash-verified:
- the staging models, the migration and its SQL views;
- `models/__init__.py` and the B1 schema tests;
- the E3-P1/P2-A code and tests;
- G01–G04 (31/31) and the Gate D research.

There was no PostgreSQL connection, migration, real import, reviewer action, commit or push.

## B1-R1: post-binding mutation

**Reproduced on the accepted B1 helper:** I bound the files, set `binding.lecturers[0]["full_name"]
= …` and adapted. The result was **COMPLETE**, with the mutated name and the original bytes SHA.

**Fix: an immutable binding plus one trusted entrypoint.** The adapter contract is unchanged.
- **`HarvestBinding`** now holds only `bytes`, `str` or `None`: the exact file bytes, the declared SHA
  and the semantic hashes. It no longer exposes `lecturers`, `manifest`, `replay` or `crawl_report`
  objects. It stays frozen with slots.
- **`build_profiles_artifact(binding)`** is the trusted path:
  1. it refuses anything that is not a `HarvestBinding` (`BINDING_REQUIRED`);
  2. it **re-verifies** the binding from its own bytes, because a `HarvestBinding` could also be built
     or `dataclasses.replace`d by hand; a forgery fails with `BYTES_SHA256_MISMATCH`,
     `MANIFEST_HASH_MISMATCH` or `BINDING_INCONSISTENT`;
  3. it decodes **fresh** objects from the verified bytes and calls `adapters.profiles_artifact`
     immediately.

  Nothing a caller holds can reach the artifact.
- **`bind_and_build_profiles_artifact(**files)`** is the single call for P2-B2.
- **Unchanged and documented:** `adapters.profiles_artifact` still trusts its input (the accepted
  P2-A contract). P2-B2 must not call it directly; a test pins this.

**Regressions:**

| Test | What it checks |
|---|---|
| `test_b1_r1_old_failure_mutating_verified_content_cannot_reach_the_artifact` | no mutable fields; frozen; a caller's mutated copy leaves `build_profiles_artifact` output identical, with the original name |
| `test_b1_r1_the_direct_adapter_path_still_trusts_its_input` | the old failure mode is still possible only on the bypass path |
| `test_b1_r1_hand_made_or_foreign_bindings_are_refused` | forged bytes, re-sealed SHA, wrong stored hash and a duck-typed look-alike are all refused |

## B1-R2: incomplete semantic replay

**Reproduced on the accepted B1 helper:** a replay with only `A_cached_write` and
`a_equals_b_equals_c = true` was **accepted**.

**The harvester's real structure** comes from Craw `ictu_harvester/full_harvest.py`,
`run_semantic_replay` and `combined_hash`, read-only, and the real `semantic_replay.json` matches it:
- `file_hashes` and `combined_hashes` have exactly the keys `A_cached_write`, `B_cached_replay` and
  `C_offline_replay`;
- `combined_hashes[p] = sha256(json.dumps(file_hashes[p], sort_keys=True,
  separators=(",", ":")))`, and recomputing this on the real file matches for all three passes;
- `combined_hash` equals the pass hashes;
- `differing_files` is `[]`.

No other pass names were introduced.

**Fix: `_check_replay`.** A replay is accepted only if all of the following hold:
- `a_equals_b_equals_c is True` and `differing_files == []`;
- `file_hashes` and `combined_hashes` have **exactly** the three passes;
- each pass is a non-empty map of names to 64-hex hashes, and its combined hash recomputes;
- every pass records the lecturers' and the manifest's semantic hashes;
- all passes cover the same file set, the combined hashes are equal, and `combined_hash` matches.

**Error codes:** `REPLAY_NOT_PASSED`, `REPLAY_PASSES_INVALID`, `REPLAY_PASS_MALFORMED` and
`REPLAY_HASH_MISMATCH`.

**Regressions:**

| Test | What it checks |
|---|---|
| `test_b1_r2_full_valid_replay_has_exactly_the_harvester_passes` | the full, valid replay is accepted |
| `…missing_extra_or_renamed_passes…` | 4 cases, including the reviewer's single pass |
| `…combined_hashes_must_cover_the_same_passes` | combined hashes cover exactly the three passes |
| `…malformed_passes…` | 5 cases: non-map, empty, non-hex, stale combined hash, wrong top-level `combined_hash` |
| `…changed_pass_hash…` | rejected whether or not the combined hash was recomputed |
| `…passes_must_agree…` | passes must cover the same files |
| `test_failed_replay_is_rejected` | 3 cases |

## Probe: accepted B1 helper against the corrected one (synthetic, same script)

| Case | Accepted B1 | Corrected |
|---|---|---|
| R1: mutate the verified lecturers, then adapt | COMPLETE, mutated name, original SHA | binding exposes no mutable content; trusted build keeps the original name |
| R2: single-pass replay, flag true | ACCEPTED | `REPLAY_PASSES_INVALID` |

**Real harvest** (read-only, booleans and counts only):
- binds through the corrected API;
- its replay passes are exactly the harvester's three;
- `build_profiles_artifact` gives 410 profiles, COMPLETE;
- truncating the real replay to one pass is rejected with `REPLAY_PASSES_INVALID`.

## Verification

| Check | Result |
|---|---|
| Pure/offline suite: E3-P1 + P2-A + B1 schema + provenance (`--noconftest`) | **247 passed**. Previously 230; the 15 old provenance tests were replaced by 32. 0 skipped, 0 xfailed |
| Provenance focused | 32 passed |
| Ruff: source_claims, staging model, migration, all 4 test files | exit 0 |
| Narrow diff `E3P2B1_CORRECTION.diff` against the accepted B1 | `provenance.py` +84/−30; test file +172/−37; whitespace clean |
| Seven-diff replay (P1 → errata → closeout → P2-A → correction → B1 → B1 correction), `--whitespace=error` | all OK; both files reproduce the workspace; reverse check OK |
| B1 models, migration, schema tests and `__init__` | 4/4 unchanged |
| Accepted E3-P1/P2-A files | 9/9 unchanged; `pyproject.toml` untouched |
| G01–G04 | 31/31 MATCH |
| `git status` | same 17 tracked modifications as after B1 |

## Remaining boundaries (unchanged)

- **Residuals:**
  - volatile harvest timestamps are bound only by the bytes SHA;
  - there is no cryptographic signature, so a party who consistently rewrites all four files is not
    detected (custody, O-2);
  - the direct adapter call remains a bypass that B2 must not use.
- **PostgreSQL:** migration execution and the G04 PostgreSQL tests are **NOT_EXECUTED**. Owner
  decisions O-2 and O-7 are still pending, and no real import is authorized.

STOPPED after the two fixes. B2 not started.
