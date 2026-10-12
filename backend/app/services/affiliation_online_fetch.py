"""Fetch public OpenAlex / Crossref / ORCID metadata for a fixed list of DOIs.

This is the ONLY place in the application that makes outbound HTTP calls for
affiliation data. It never takes a URL or host from a request — only DOIs
(validated, loopback-safe) already present in the database — and writes
nothing except the bundle files consumed by ``affiliation_sources.py``:

    openalex_works.jsonl   — one line per DOI: {"retrieved_at", "source",
                              "query_doi", "work": <raw OpenAlex work object>}
    crossref_works.jsonl   — one line per DOI: {"retrieved_at", "source",
                              "query_doi", "http", "work"?: <raw Crossref message subset>}
    orcid_external_ids.json — {orcid: {"retrieved_at", "http",
                              "external_identifiers": [...]}}

The three ``work``/record shapes are written verbatim from each API's own
response so ``parse_openalex_authorships`` / ``parse_crossref_authors`` /
``parse_orcid_scopus_ids`` in ``author_affiliation.py`` can read them exactly
as they already read a hand-built offline bundle — no new parsing branch.

Safety:
* a fixed, hard-coded allow-list of three hosts — never a caller-supplied URL;
* batch size and per-run DOI cap come from server settings, never a request;
* bounded retries with exponential backoff only on 429/5xx/timeout;
* an explicit per-call timeout; a request is never left to hang;
* an in-process cache keyed by (source, normalized DOI) so a retry or a
  second run never re-queries a DOI already answered in this run;
* no credentials are sent or logged — these APIs are used anonymously.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import urllib.parse
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx2 as httpx

logger = logging.getLogger(__name__)

USER_AGENT = "scopus-ictu-affiliation-enrichment/1.0 (academic thesis project; no personal data requested)"
_TIMEOUT_SECONDS = 20.0
_MAX_RETRIES = 3
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_OPENALEX_BATCH_SIZE = 40
_OPENALEX_RATE_DELAY = 0.25  # <=4 req/s, well under OpenAlex's documented polite-pool limits
_CROSSREF_RATE_DELAY = 0.35
_ORCID_RATE_DELAY = 0.30

OPENALEX_BASE = "https://api.openalex.org"
CROSSREF_BASE = "https://api.crossref.org"
ORCID_BASE = "https://pub.orcid.org/v3.0"
_ALLOWED_HOSTS = frozenset({"api.openalex.org", "api.crossref.org", "pub.orcid.org"})

_DOI_RE = re.compile(r"^10\.\d+/\S+$")


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().lower()
    v = v.removeprefix("https://doi.org/").removeprefix("http://doi.org/").removeprefix("doi:")
    return v if _DOI_RE.match(v) else None


@dataclass(slots=True)
class FetchProgress:
    total: int
    done: int = 0
    openalex_found: int = 0
    crossref_found: int = 0
    orcid_fetched: int = 0


@dataclass(slots=True)
class FetchResult:
    bundle_dir: Path
    stats: dict[str, Any] = field(default_factory=dict)


class AffiliationFetchCancelled(Exception):
    """Raised by the caller-supplied ``should_continue`` to stop the run cleanly."""


async def _get_json(
    client: httpx.AsyncClient, url: str, *, params: dict | None = None
) -> tuple[int, Any]:
    host = httpx.URL(url).host
    if host not in _ALLOWED_HOSTS:
        raise ValueError(f"host not in allow-list: {host}")
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = await client.get(url, params=params, timeout=_TIMEOUT_SECONDS)
        except (httpx.TimeoutException, httpx.TransportError):
            if attempt == _MAX_RETRIES:
                return 0, None
            await asyncio.sleep(2**attempt)
            continue
        if resp.status_code in _RETRY_STATUS and attempt < _MAX_RETRIES:
            await asyncio.sleep(2**attempt)
            continue
        if resp.status_code >= 400:
            return resp.status_code, None
        try:
            return resp.status_code, resp.json()
        except ValueError:
            return resp.status_code, None
    return 0, None


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def fetch_openalex_works(
    client: httpx.AsyncClient,
    dois: Sequence[str],
    *,
    cache: dict[str, dict] | None = None,
    on_record: Callable[[dict], Awaitable[None]] | None = None,
    should_continue: Callable[[], bool] | None = None,
) -> int:
    """Write one JSONL line per input DOI (found or not) via ``on_record``."""

    cache = cache if cache is not None else {}
    found = 0
    for i in range(0, len(dois), _OPENALEX_BATCH_SIZE):
        if should_continue is not None and not should_continue():
            raise AffiliationFetchCancelled
        chunk = [d for d in dois[i : i + _OPENALEX_BATCH_SIZE] if d not in cache]
        by_doi: dict[str, dict] = {}
        if chunk:
            url = f"{OPENALEX_BASE}/works"
            params = {
                "filter": "doi:" + "|".join(chunk),
                "per-page": 50,
                "select": "id,doi,title,publication_year,authorships",
            }
            _status, data = await _get_json(client, url, params=params)
            for work in (data or {}).get("results", []) or []:
                doi = (work.get("doi") or "").replace("https://doi.org/", "").lower()
                if doi:
                    by_doi[doi] = work
            await asyncio.sleep(_OPENALEX_RATE_DELAY)
        for doi in dois[i : i + _OPENALEX_BATCH_SIZE]:
            if doi in cache:
                record = cache[doi]
            else:
                work = by_doi.get(doi)
                record = {
                    "retrieved_at": _now(),
                    "source": "openalex",
                    "query_doi": doi,
                    "work": work,
                }
                cache[doi] = record
            if record.get("work"):
                found += 1
            if on_record is not None:
                await on_record(record)
    return found


async def fetch_crossref_works(
    client: httpx.AsyncClient,
    dois: Sequence[str],
    *,
    cache: dict[str, dict] | None = None,
    on_record: Callable[[dict], Awaitable[None]] | None = None,
    should_continue: Callable[[], bool] | None = None,
) -> int:
    cache = cache if cache is not None else {}
    found = 0
    keep_fields = ("DOI", "title", "author", "publisher", "type", "issued")
    for doi in dois:
        if should_continue is not None and not should_continue():
            raise AffiliationFetchCancelled
        if doi in cache:
            record = cache[doi]
        else:
            url = f"{CROSSREF_BASE}/works/{urllib.parse.quote(doi, safe='/()')}"
            status, data = await _get_json(client, url)
            record: dict[str, Any] = {
                "retrieved_at": _now(),
                "source": "crossref",
                "query_doi": doi,
                "http": status,
            }
            message = (data or {}).get("message") if data else None
            if message:
                record["work"] = {k: message.get(k) for k in keep_fields}
            cache[doi] = record
            await asyncio.sleep(_CROSSREF_RATE_DELAY)
        if record.get("work"):
            found += 1
        if on_record is not None:
            await on_record(record)
    return found


def _extract_orcids(openalex_records: Sequence[dict], crossref_records: Sequence[dict]) -> list[str]:
    orcid_re = re.compile(r"(\d{4}-\d{4}-\d{4}-\d{3}[\dX])")
    found: set[str] = set()
    for rec in openalex_records:
        work = rec.get("work") or {}
        for a in work.get("authorships") or []:
            orcid = (a.get("author") or {}).get("orcid")
            if orcid:
                m = orcid_re.search(orcid)
                if m:
                    found.add(m.group(1))
    for rec in crossref_records:
        work = rec.get("work") or {}
        for a in work.get("author") or []:
            orcid = a.get("ORCID")
            if orcid:
                m = orcid_re.search(orcid)
                if m:
                    found.add(m.group(1))
    return sorted(found)


async def fetch_orcid_records(
    client: httpx.AsyncClient,
    orcids: Sequence[str],
    *,
    cache: dict[str, dict] | None = None,
    should_continue: Callable[[], bool] | None = None,
) -> dict[str, dict]:
    cache = cache if cache is not None else {}
    out: dict[str, dict] = {}
    for orcid in orcids:
        if should_continue is not None and not should_continue():
            raise AffiliationFetchCancelled
        if orcid in cache:
            out[orcid] = cache[orcid]
            continue
        url = f"{ORCID_BASE}/{orcid}/external-identifiers"
        status, data = await _get_json(client, url)
        if data is not None:
            record = {
                "retrieved_at": _now(),
                "http": status,
                "external_identifiers": [
                    {
                        "type": x.get("external-id-type"),
                        "value": x.get("external-id-value"),
                        "url": (x.get("external-id-url") or {}).get("value"),
                        "source": ((x.get("source") or {}).get("source-name") or {}).get("value"),
                    }
                    for x in (data.get("external-identifier") or [])
                ],
            }
        else:
            record = {"retrieved_at": _now(), "http": status, "external_identifiers": None}
        cache[orcid] = record
        out[orcid] = record
        await asyncio.sleep(_ORCID_RATE_DELAY)
    return out


async def run_enrichment(
    bundle_dir: Path,
    dois: Sequence[str],
    *,
    progress_cb: Callable[[FetchProgress], Awaitable[None]] | None = None,
    should_continue: Callable[[], bool] | None = None,
) -> FetchResult:
    """Fetch and write a full bundle (openalex + crossref + orcid) for ``dois``.

    ``dois`` must already be normalized/deduplicated by the caller. Writes
    into ``bundle_dir`` (created if missing) — never a path derived from
    request input.
    """

    bundle_dir.mkdir(parents=True, exist_ok=True)
    progress = FetchProgress(total=len(dois))
    openalex_records: list[dict] = []
    crossref_records: list[dict] = []

    async def on_openalex(record: dict) -> None:
        openalex_records.append(record)
        if record.get("work"):
            progress.openalex_found += 1

    async def on_crossref(record: dict) -> None:
        crossref_records.append(record)
        if record.get("work"):
            progress.crossref_found += 1
        progress.done += 1
        if progress_cb is not None:
            await progress_cb(progress)

    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT, "Accept": "application/json"}) as client:
        await fetch_openalex_works(client, dois, on_record=on_openalex, should_continue=should_continue)
        await fetch_crossref_works(client, dois, on_record=on_crossref, should_continue=should_continue)
        orcids = _extract_orcids(openalex_records, crossref_records)
        orcid_records = await fetch_orcid_records(client, orcids, should_continue=should_continue)
        progress.orcid_fetched = len(orcid_records)
        if progress_cb is not None:
            await progress_cb(progress)

    with (bundle_dir / "openalex_works.jsonl").open("w", encoding="utf-8") as fh:
        for rec in openalex_records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    with (bundle_dir / "crossref_works.jsonl").open("w", encoding="utf-8") as fh:
        for rec in crossref_records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    (bundle_dir / "orcid_external_ids.json").write_text(
        json.dumps(orcid_records, ensure_ascii=False), encoding="utf-8"
    )

    stats = {
        "total_dois": len(dois),
        "openalex_found": progress.openalex_found,
        "crossref_found": progress.crossref_found,
        "orcid_fetched": progress.orcid_fetched,
    }
    return FetchResult(bundle_dir=bundle_dir, stats=stats)


__all__ = [
    "AffiliationFetchCancelled",
    "FetchProgress",
    "FetchResult",
    "normalize_doi",
    "run_enrichment",
]
