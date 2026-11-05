"""Parsers only parse. No DB writes, no business logic."""

from app.services.parser.scopus_csv_parser import ScopusCsvParser

__all__ = ["ScopusCsvParser"]
