"""Bind harvest file bytes to their manifest and semantic replay, then adapt only those bytes.

A binding holds immutable bytes and hashes; ``build_profiles_artifact`` decodes fresh objects from
them and adapts in one step. P2-B2 must not call ``adapters.profiles_artifact`` directly.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from app.services.source_claims import adapters

# Craw ``ictu_harvester.full_harvest.semantic_hash``: keys dropped at every level before hashing.
HARVEST_VOLATILE_KEYS = frozenset({"retrieved_at", "harvest_started_at", "harvest_completed_at",
                                   "last_attempt_time"})
MANIFEST_NAME = "harvest_manifest.json"
# Craw ``ictu_harvester.full_harvest.run_semantic_replay``: exactly these three passes are written,
# each pass's combined hash is sha256 over its sorted, compact file-hash map.
REPLAY_PASSES = frozenset({"A_cached_write", "B_cached_replay", "C_offline_replay"})
_HEX64 = re.compile(r"[0-9a-f]{64}")


class ProvenanceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True, slots=True)
class HarvestBinding:
    """Verified harvest files. Only immutable bytes and hashes; decode via ``build_*``."""

    upstream_name: str
    lecturers_bytes: bytes
    manifest_bytes: bytes
    replay_bytes: bytes
    crawl_report_bytes: bytes | None
    lecturers_sha256: str
    lecturers_semantic_sha256: str
    manifest_semantic_sha256: str


def _without_volatile(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _without_volatile(v) for k, v in value.items() if k not in HARVEST_VOLATILE_KEYS}
    if isinstance(value, list):
        return [_without_volatile(v) for v in value]
    return value


def harvest_semantic_hash(value: Any) -> str:
    """Reproduces the harvester's semantic hash (sorted, compact, non-ASCII kept)."""
    encoded = json.dumps(_without_volatile(value), ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _replay_combined_hash(file_hashes: dict) -> str:
    """Craw ``combined_hash``: json.dumps(sort_keys, compact) with default ASCII escaping."""
    return hashlib.sha256(
        json.dumps(file_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _decode(data: bytes, name: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        duplicated = sorted(k for k, n in Counter(k for k, _ in pairs).items() if n > 1)
        if duplicated:
            raise ProvenanceError("DUPLICATE_JSON_KEY", f"{name}: duplicate keys {duplicated}")
        return dict(pairs)

    if not isinstance(data, bytes):
        raise ProvenanceError("BYTES_REQUIRED", f"{name} must be passed as the exact file bytes")
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except UnicodeDecodeError as exc:
        raise ProvenanceError("NOT_UTF8", name) from exc
    except json.JSONDecodeError as exc:
        raise ProvenanceError("NOT_JSON", f"{name}: {exc}") from exc


def _check_replay(replay: dict, expected: dict[str, str]) -> None:
    """The replay must have exactly the harvester's three passes, all well formed and equal."""
    if replay.get("a_equals_b_equals_c") is not True or replay.get("differing_files") != []:
        raise ProvenanceError("REPLAY_NOT_PASSED", "semantic replay did not pass")
    passes, combined = replay.get("file_hashes"), replay.get("combined_hashes")
    if not isinstance(passes, dict) or set(passes) != REPLAY_PASSES:
        raise ProvenanceError("REPLAY_PASSES_INVALID",
                              f"replay passes must be exactly {sorted(REPLAY_PASSES)}")
    if not isinstance(combined, dict) or set(combined) != REPLAY_PASSES:
        raise ProvenanceError("REPLAY_PASSES_INVALID",
                              "combined_hashes must cover exactly the same passes")
    file_sets = set()
    for name in sorted(REPLAY_PASSES):
        run = passes[name]
        if not isinstance(run, dict) or not run or not all(
                isinstance(k, str) and isinstance(v, str) and _HEX64.fullmatch(v)
                for k, v in run.items()):
            raise ProvenanceError("REPLAY_PASS_MALFORMED", f"replay pass {name} is malformed")
        if combined[name] != _replay_combined_hash(run):
            raise ProvenanceError("REPLAY_PASS_MALFORMED",
                                  f"replay pass {name} does not match its combined hash")
        if any(run.get(file) != digest for file, digest in expected.items()):
            raise ProvenanceError("REPLAY_HASH_MISMATCH",
                                  f"replay pass {name} does not describe these files")
        file_sets.add(frozenset(run))
    if len(file_sets) != 1 or len(set(combined.values())) != 1 \
            or replay.get("combined_hash") not in set(combined.values()):
        raise ProvenanceError("REPLAY_PASS_MALFORMED", "replay passes disagree with each other")


def bind_harvest_files(
    *, lecturers_bytes: bytes, lecturers_sha256: str, manifest_bytes: bytes, replay_bytes: bytes,
    crawl_report_bytes: bytes | None = None, upstream_name: str = "lecturers.json",
) -> HarvestBinding:
    """Prove bytes ↔ declared SHA ↔ manifest ↔ every replay pass (↔ crawl report); else raise."""
    lecturers = _decode(lecturers_bytes, upstream_name)
    if hashlib.sha256(lecturers_bytes).hexdigest() != lecturers_sha256:
        raise ProvenanceError("BYTES_SHA256_MISMATCH",
                              f"{upstream_name} bytes do not hash to the declared SHA-256")
    manifest = _decode(manifest_bytes, MANIFEST_NAME)
    replay = _decode(replay_bytes, "semantic_replay.json")
    if not isinstance(manifest, dict) or not isinstance(replay, dict):
        raise ProvenanceError("NOT_OBJECT", "manifest and semantic replay must be JSON objects")

    lecturers_semantic = harvest_semantic_hash(lecturers)
    if (manifest.get("semantic_file_hashes") or {}).get(upstream_name) != lecturers_semantic:
        raise ProvenanceError("MANIFEST_HASH_MISMATCH",
                              f"{upstream_name} is not the file this manifest describes")
    manifest_semantic = harvest_semantic_hash(manifest)
    _check_replay(replay, {upstream_name: lecturers_semantic, MANIFEST_NAME: manifest_semantic})

    if crawl_report_bytes is not None:
        crawl_report = _decode(crawl_report_bytes, "crawl_report.json")
        expected = (manifest.get("semantic_file_hashes") or {}).get("crawl_report.json")
        if harvest_semantic_hash(crawl_report) != expected:
            raise ProvenanceError("MANIFEST_HASH_MISMATCH",
                                  "crawl_report.json is not the report this manifest describes")

    return HarvestBinding(upstream_name, lecturers_bytes, manifest_bytes, replay_bytes,
                          crawl_report_bytes, lecturers_sha256, lecturers_semantic,
                          manifest_semantic)


def build_profiles_artifact(binding: HarvestBinding) -> dict:
    """The trusted path: decode fresh objects from the verified bytes and adapt them at once."""
    if not isinstance(binding, HarvestBinding):
        raise ProvenanceError("BINDING_REQUIRED", "pass the result of bind_harvest_files")
    # Re-verify: a HarvestBinding can also be constructed by hand, bypassing bind_harvest_files.
    if bind_harvest_files(
            lecturers_bytes=binding.lecturers_bytes, lecturers_sha256=binding.lecturers_sha256,
            manifest_bytes=binding.manifest_bytes, replay_bytes=binding.replay_bytes,
            crawl_report_bytes=binding.crawl_report_bytes,
            upstream_name=binding.upstream_name) != binding:
        raise ProvenanceError("BINDING_INCONSISTENT", "binding hashes do not match its bytes")
    crawl_report = (None if binding.crawl_report_bytes is None
                    else _decode(binding.crawl_report_bytes, "crawl_report.json"))
    return adapters.profiles_artifact(
        _decode(binding.lecturers_bytes, binding.upstream_name),
        _decode(binding.manifest_bytes, MANIFEST_NAME), crawl_report,
        _decode(binding.replay_bytes, "semantic_replay.json"),
        lecturers_sha256=binding.lecturers_sha256, upstream_name=binding.upstream_name)


def bind_and_build_profiles_artifact(**files: Any) -> dict:
    """``bind_harvest_files`` then ``build_profiles_artifact``; the entrypoint for P2-B2."""
    return build_profiles_artifact(bind_harvest_files(**files))
