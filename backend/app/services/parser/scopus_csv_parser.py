"""Strict, lossless parser for raw Scopus CSV uploads."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from dataclasses import dataclass


class ScopusCsvError(ValueError):
    """Safe parser failure with a stable public machine code."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ParsedScopusRow:
    row_number: int
    row_hash: str
    eid_raw: str | None
    doi_raw: str | None
    raw_payload: dict[str, str]


@dataclass(frozen=True)
class ParsedScopusRowError:
    """A recoverable row error whose original values are retained."""

    row_number: int
    row_hash: str
    raw_values: tuple[str, ...]
    code: str
    message: str


@dataclass(frozen=True)
class ParsedScopusFile:
    headers: tuple[str, ...]
    rows: tuple[ParsedScopusRow, ...]
    row_errors: tuple[ParsedScopusRowError, ...]
    total_records: int
    duplicate_candidates: int
    duplicate_row_numbers: tuple[int, ...]


class ScopusCsvParser:
    """Parse CSV without normalizing or discarding source values."""

    def parse_bytes(self, content: bytes) -> ParsedScopusFile:
        if not content:
            raise ScopusCsvError("EMPTY_IMPORT_FILE", "Tệp tải lên không có dữ liệu.")

        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ScopusCsvError(
                "INVALID_CSV",
                "Không thể đọc tệp CSV. Tệp phải sử dụng mã hóa UTF-8.",
            ) from exc

        try:
            reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
            headers = next(reader)
        except StopIteration as exc:
            raise ScopusCsvError("MISSING_HEADER", "Tệp CSV không có dòng tiêu đề.") from exc
        except csv.Error as exc:
            raise ScopusCsvError("INVALID_CSV", "Cấu trúc tệp CSV không hợp lệ.") from exc

        self._validate_headers(headers)
        header_tuple = tuple(headers)
        lookup = {header.strip().casefold(): header for header in header_tuple}
        rows: list[ParsedScopusRow] = []
        row_errors: list[ParsedScopusRowError] = []
        seen_hashes: set[str] = set()
        seen_eids: set[str] = set()
        duplicate_row_numbers: list[int] = []

        try:
            for values in reader:
                source_row_number = reader.line_num
                if not values or all(not value.strip() for value in values):
                    continue
                serialized = json.dumps(
                    values,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                ).encode("utf-8")
                row_hash = hashlib.sha256(serialized).hexdigest()
                if len(values) != len(header_tuple):
                    row_errors.append(
                        ParsedScopusRowError(
                            row_number=source_row_number,
                            row_hash=row_hash,
                            raw_values=tuple(values),
                            code="COLUMN_COUNT_MISMATCH",
                            message=(
                                f"Dòng {source_row_number} có {len(values)} cột; "
                                f"cần {len(header_tuple)} cột."
                            ),
                        )
                    )
                    continue

                payload = dict(zip(header_tuple, values, strict=True))
                eid_header = lookup.get("eid")
                doi_header = lookup.get("doi")
                eid_raw = payload[eid_header] if eid_header else None
                doi_raw = payload[doi_header] if doi_header else None

                normalized_eid = eid_raw.strip() if eid_raw else None
                is_duplicate = row_hash in seen_hashes or (
                    normalized_eid is not None and normalized_eid in seen_eids
                )
                if is_duplicate:
                    duplicate_row_numbers.append(source_row_number)
                seen_hashes.add(row_hash)
                if normalized_eid:
                    seen_eids.add(normalized_eid)

                rows.append(
                    ParsedScopusRow(
                        row_number=source_row_number,
                        row_hash=row_hash,
                        eid_raw=eid_raw or None,
                        doi_raw=doi_raw or None,
                        raw_payload=payload,
                    )
                )
        except csv.Error as exc:
            raise ScopusCsvError("INVALID_CSV", "Cấu trúc tệp CSV không hợp lệ.") from exc

        if not rows and not row_errors:
            raise ScopusCsvError(
                "INVALID_CSV",
                "Tệp CSV phải có ít nhất một dòng dữ liệu.",
            )
        total_records = len(rows) + len(row_errors)
        return ParsedScopusFile(
            headers=header_tuple,
            rows=tuple(rows),
            row_errors=tuple(row_errors),
            total_records=total_records,
            duplicate_candidates=len(duplicate_row_numbers),
            duplicate_row_numbers=tuple(duplicate_row_numbers),
        )

    @staticmethod
    def _validate_headers(headers: list[str]) -> None:
        if not headers or all(not header.strip() for header in headers):
            raise ScopusCsvError("MISSING_HEADER", "Tệp CSV không có dòng tiêu đề.")
        if any(not header.strip() or "\x00" in header for header in headers):
            raise ScopusCsvError(
                "INVALID_CSV_HEADER",
                "Tiêu đề CSV không được để trống.",
            )
        if any(count > 1 for count in Counter(headers).values()):
            raise ScopusCsvError(
                "INVALID_CSV_HEADER",
                "Tệp CSV có tên cột bị trùng lặp.",
            )


__all__ = [
    "ParsedScopusFile",
    "ParsedScopusRow",
    "ParsedScopusRowError",
    "ScopusCsvError",
    "ScopusCsvParser",
]
