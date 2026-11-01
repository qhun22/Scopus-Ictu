"""Gate E.3 / P2-B1 — input-file trust boundary for the future P2-B2 file reader.

Synthetic harvest bundles only, shaped like Craw's ``run_semantic_replay`` output. The adapter
trusts the objects it is given; the binding and its bind-and-adapt entrypoint must not.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

from app.services.source_claims import adapters
from app.services.source_claims.provenance import (
    MANIFEST_NAME,
    REPLAY_PASSES,
    HarvestBinding,
    ProvenanceError,
    bind_and_build_profiles_artifact,
    bind_harvest_files,
    build_profiles_artifact,
    harvest_semantic_hash,
)

BACKEND = Path(__file__).resolve().parents[2]
REPO = "https://repository.example.invalid"
PASSES = ("A_cached_write", "B_cached_replay", "C_offline_replay")


def _lecturer(n, retrieved="2026-10-03T18:44:10Z"):
    url = f"{REPO}/giang-vien/synthetic-{n}/"
    return {"source_id": url, "full_name": f"Synthetic {n}",
            "institutional_email": f"l{n}@example.invalid", "orcid": None,
            "provenance": {"source_url": url, "retrieved_at": retrieved}}


def _encode(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _combined(file_hashes: dict) -> str:
    return hashlib.sha256(json.dumps(file_hashes, sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def _replay(file_hashes: dict, *, passes=PASSES, ok=True) -> dict:
    """Same structure as Craw ``run_semantic_replay``."""
    runs = {run: dict(file_hashes) for run in passes}
    combined = {run: _combined(hashes) for run, hashes in runs.items()}
    return {"file_hashes": runs, "combined_hashes": combined,
            "combined_hash": combined[passes[0]] if passes else "0" * 64,
            "a_equals_b_equals_c": ok, "differing_files": [],
            "network_requests": {"A": 0, "B": 0, "C": 0}, "scope_note": "synthetic"}


def bundle(lecturers=None, *, replay_ok=True):
    lecturers = lecturers if lecturers is not None else [_lecturer(1), _lecturer(2)]
    crawl = {"source_entity_failures": [], "duplicate_profile_url_count": 0}
    manifest = {"harvest_started_at": "2026-10-03T20:05:14Z",
                "harvest_completed_at": "2026-10-03T21:31:10Z", "source_base_url": REPO,
                "source_card_count": len(lecturers), "lecturer_count": len(lecturers),
                "status": "COMPLETE", "source_drift_detected": False,
                "semantic_file_hashes": {"lecturers.json": harvest_semantic_hash(lecturers),
                                         "crawl_report.json": harvest_semantic_hash(crawl)}}
    file_hashes = {"lecturers.json": harvest_semantic_hash(lecturers),
                   "crawl_report.json": harvest_semantic_hash(crawl),
                   MANIFEST_NAME: harvest_semantic_hash(manifest)}
    replay = _replay(file_hashes, ok=replay_ok)
    files = {"lecturers": _encode(lecturers), "manifest": _encode(manifest),
             "replay": _encode(replay), "crawl": _encode(crawl)}
    files["sha"] = hashlib.sha256(files["lecturers"]).hexdigest()
    return files


def _args(files, **overrides):
    args = {"lecturers_bytes": files["lecturers"], "lecturers_sha256": files["sha"],
            "manifest_bytes": files["manifest"], "replay_bytes": files["replay"],
            "crawl_report_bytes": files["crawl"]}
    args.update(overrides)
    return args


def bind(files, **overrides):
    return bind_harvest_files(**_args(files, **overrides))


def _code(call) -> str:
    with pytest.raises(ProvenanceError) as raised:
        call()
    return raised.value.code


def _replay_of(files) -> dict:
    return json.loads(files["replay"])


# ---------------------------------------------------------------------------
# Binding basics
# ---------------------------------------------------------------------------

def test_consistent_harvest_files_bind_and_build_a_complete_artifact():
    files = bundle()
    artifact = build_profiles_artifact(bind(files))
    assert artifact["capture"]["completeness"] == "COMPLETE"
    assert artifact["capture"]["upstream"]["bytes_sha256"] == files["sha"]
    assert [p["full_name"] for p in artifact["content"]["profiles"]] == ["Synthetic 1",
                                                                         "Synthetic 2"]
    assert bind_and_build_profiles_artifact(**_args(files)) == artifact


def test_declared_sha256_must_be_the_hash_of_the_bytes_read():
    assert _code(lambda: bind(bundle(), lecturers_sha256="f" * 64)) == "BYTES_SHA256_MISMATCH"


def test_other_lecturers_file_with_its_own_correct_sha_is_rejected_by_the_manifest():
    files = bundle()
    forged = _encode([_lecturer(1), _lecturer(3)])
    code = _code(lambda: bind(files, lecturers_bytes=forged,
                              lecturers_sha256=hashlib.sha256(forged).hexdigest()))
    assert code == "MANIFEST_HASH_MISMATCH"


def test_edited_manifest_is_rejected_by_the_replay():
    files = bundle()
    manifest = json.loads(files["manifest"])
    manifest["source_card_count"] += 1
    assert _code(lambda: bind(files, manifest_bytes=_encode(manifest))) == "REPLAY_HASH_MISMATCH"


def test_edited_crawl_report_is_rejected():
    files = bundle()
    crawl = json.loads(files["crawl"])
    crawl["source_entity_failures"] = [{"entity_type": "lecturer"}]
    assert _code(lambda: bind(files, crawl_report_bytes=_encode(crawl))) == (
        "MANIFEST_HASH_MISMATCH")


# ---------------------------------------------------------------------------
# B1-R1: no mutation between verification and use
# ---------------------------------------------------------------------------

def test_b1_r1_old_failure_mutating_verified_content_cannot_reach_the_artifact():
    """Reviewer reproduction: bind, mutate a lecturer's name, adapt -> COMPLETE with the original
    SHA. The binding no longer exposes mutable content, and the trusted path decodes fresh."""
    files = bundle()
    binding = bind(files)
    assert not hasattr(binding, "lecturers")
    for field in dataclasses.fields(HarvestBinding):
        assert isinstance(getattr(binding, field.name), (bytes, str, type(None))), field.name
    with pytest.raises(dataclasses.FrozenInstanceError):
        binding.lecturers_bytes = b"[]"

    expected = build_profiles_artifact(binding)
    decoded = json.loads(binding.lecturers_bytes)      # a caller's own copy ...
    decoded[0]["full_name"] = "Changed After Verification"   # ... mutated after the check
    after = build_profiles_artifact(binding)
    assert after == expected
    assert after["content"]["profiles"][0]["full_name"] == "Synthetic 1"


def test_b1_r1_the_direct_adapter_path_still_trusts_its_input():
    """Why P2-B2 must use build_profiles_artifact: the adapter alone keeps its P2-A contract."""
    files = bundle()
    binding = bind(files)
    tampered = json.loads(binding.lecturers_bytes)
    tampered[0]["full_name"] = "Changed After Verification"
    direct = adapters.profiles_artifact(
        tampered, json.loads(binding.manifest_bytes), json.loads(binding.crawl_report_bytes),
        json.loads(binding.replay_bytes), lecturers_sha256=binding.lecturers_sha256)
    assert direct["capture"]["completeness"] == "COMPLETE"            # the old failure mode
    assert direct["content"] != build_profiles_artifact(binding)["content"]


def test_b1_r1_hand_made_or_foreign_bindings_are_refused():
    files = bundle()
    binding = bind(files)
    forged_bytes = _encode([_lecturer(1), _lecturer(9)])
    forged = dataclasses.replace(binding, lecturers_bytes=forged_bytes)
    assert _code(lambda: build_profiles_artifact(forged)) == "BYTES_SHA256_MISMATCH"
    resealed = dataclasses.replace(forged,
                                   lecturers_sha256=hashlib.sha256(forged_bytes).hexdigest())
    assert _code(lambda: build_profiles_artifact(resealed)) == "MANIFEST_HASH_MISMATCH"
    wrong_hash = dataclasses.replace(binding, manifest_semantic_sha256="0" * 64)
    assert _code(lambda: build_profiles_artifact(wrong_hash)) == "BINDING_INCONSISTENT"
    lookalike = types.SimpleNamespace(**{f.name: getattr(binding, f.name)
                                         for f in dataclasses.fields(HarvestBinding)})
    assert _code(lambda: build_profiles_artifact(lookalike)) == "BINDING_REQUIRED"


# ---------------------------------------------------------------------------
# B1-R2: the replay must be the harvester's complete three-pass replay
# ---------------------------------------------------------------------------

def test_b1_r2_full_valid_replay_has_exactly_the_harvester_passes():
    files = bundle()
    assert set(_replay_of(files)["file_hashes"]) == REPLAY_PASSES == set(PASSES)
    bind(files)


@pytest.mark.parametrize("passes", [("A_cached_write",),                       # reviewer case
                                    ("A_cached_write", "B_cached_replay"),
                                    (*PASSES, "D_extra_replay"),
                                    ("A", "B", "C")])
def test_b1_r2_missing_extra_or_renamed_passes_are_rejected(passes):
    files = bundle()
    replay = _replay(_replay_of(files)["file_hashes"]["A_cached_write"], passes=passes)
    assert replay["a_equals_b_equals_c"] is True
    assert _code(lambda: bind(files, replay_bytes=_encode(replay))) == "REPLAY_PASSES_INVALID"


def test_b1_r2_combined_hashes_must_cover_the_same_passes():
    files = bundle()
    replay = _replay_of(files)
    del replay["combined_hashes"]["C_offline_replay"]
    assert _code(lambda: bind(files, replay_bytes=_encode(replay))) == "REPLAY_PASSES_INVALID"


@pytest.mark.parametrize("corrupt", [
    lambda r: r["file_hashes"].update(B_cached_replay=["not", "a", "map"]),
    lambda r: r["file_hashes"].update(B_cached_replay={}),
    lambda r: r["file_hashes"]["B_cached_replay"].update({"lecturers.json": "not-hex"}),
    lambda r: r["file_hashes"]["B_cached_replay"].update({"extra.json": "1" * 64}),  # stale
    lambda r: r.update(combined_hash="2" * 64),
])
def test_b1_r2_malformed_passes_are_rejected(corrupt):
    files = bundle()
    replay = _replay_of(files)
    corrupt(replay)
    assert _code(lambda: bind(files, replay_bytes=_encode(replay))) == "REPLAY_PASS_MALFORMED"


def test_b1_r2_changed_pass_hash_is_rejected_even_with_a_recomputed_combined_hash():
    files = bundle()
    replay = _replay_of(files)
    replay["file_hashes"]["C_offline_replay"]["lecturers.json"] = "0" * 64
    stale = copy.deepcopy(replay)
    assert _code(lambda: bind(files, replay_bytes=_encode(stale))) == "REPLAY_PASS_MALFORMED"
    replay["combined_hashes"]["C_offline_replay"] = _combined(
        replay["file_hashes"]["C_offline_replay"])
    assert _code(lambda: bind(files, replay_bytes=_encode(replay))) == "REPLAY_HASH_MISMATCH"


def test_b1_r2_passes_must_agree_with_each_other():
    files = bundle()
    replay = _replay_of(files)
    replay["file_hashes"]["B_cached_replay"]["other.json"] = "3" * 64
    replay["combined_hashes"]["B_cached_replay"] = _combined(
        replay["file_hashes"]["B_cached_replay"])
    assert _code(lambda: bind(files, replay_bytes=_encode(replay))) == "REPLAY_PASS_MALFORMED"


@pytest.mark.parametrize("corrupt", [lambda r: r.update(a_equals_b_equals_c=False),
                                     lambda r: r.update(differing_files=["lecturers.json"]),
                                     lambda r: r.pop("differing_files")])
def test_failed_replay_is_rejected(corrupt):
    files = bundle()
    replay = _replay_of(files)
    corrupt(replay)
    assert _code(lambda: bind(files, replay_bytes=_encode(replay))) == "REPLAY_NOT_PASSED"


# ---------------------------------------------------------------------------
# Residuals, malformed input, purity
# ---------------------------------------------------------------------------

def test_volatile_timestamps_are_bound_only_by_the_byte_hash():
    files = bundle()
    retimed = _encode([_lecturer(1, "2030-01-01T00:00:00Z"), _lecturer(2)])
    assert _code(lambda: bind(files, lecturers_bytes=retimed)) == "BYTES_SHA256_MISMATCH"
    rebound = bind(files, lecturers_bytes=retimed,
                   lecturers_sha256=hashlib.sha256(retimed).hexdigest())
    assert rebound.lecturers_semantic_sha256 == bind(files).lecturers_semantic_sha256


@pytest.mark.parametrize(("override", "code"), [
    ({"lecturers_bytes": b'[{"source_id": "a", "source_id": "b"}]'}, "DUPLICATE_JSON_KEY"),
    ({"lecturers_bytes": b"\xff\xfe"}, "NOT_UTF8"),
    ({"manifest_bytes": b"{"}, "NOT_JSON"),
    ({"manifest_bytes": b"[]"}, "NOT_OBJECT"),
    ({"lecturers_bytes": "[]"}, "BYTES_REQUIRED"),
])
def test_malformed_files_are_rejected(override, code):
    assert _code(lambda: bind(bundle(), **override)) == code


def test_semantic_hash_drops_volatile_keys_at_every_level():
    a = {"x": 1, "retrieved_at": "t1", "nested": [{"last_attempt_time": "t2", "y": 2}]}
    b = {"nested": [{"y": 2}], "x": 1}
    assert harvest_semantic_hash(a) == harvest_semantic_hash(b)
    assert harvest_semantic_hash({"x": 1}) != harvest_semantic_hash({"x": 2})


def test_provenance_imports_no_database_app_or_network_modules():
    bad = ("sqlalchemy", "psycopg2", "fastapi", "pydantic_settings", "app.main", "app.core",
           "app.models", "app.api", "requests", "httpx", "urllib.request", "http.client",
           "socket")
    code = (
        "import json, sys; sys.path.insert(0, '.');"
        f"bad = {bad!r};"
        "hit = lambda names: sorted(m for m in names"
        " if any(m == b or m.startswith(b + '.') for b in bad));"
        "before = set(sys.modules);"
        "import app.services.source_claims.provenance;"
        "print(json.dumps({'new': hit(set(sys.modules) - before)}))"
    )
    result = subprocess.run([sys.executable, "-I", "-S", "-c", code], cwd=BACKEND,
                            capture_output=True, text=True, timeout=60, check=True)
    assert json.loads(result.stdout)["new"] == [], result.stdout + result.stderr
