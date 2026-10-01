"""Normalizers — M0 scaffold.

Normalizers perform deterministic normalization. No I/O, no DB access.
"""

from app.services.normalization.doi_normalizer import DoiNormalizer
from app.services.normalization.name_normalizer import NameNormalizer
from app.services.normalization.orcid_normalizer import OrcidNormalizer
from app.services.normalization.text_normalizer import TextNormalizer
from app.services.normalization.title_normalizer import TitleNormalizer

__all__ = [
    "DoiNormalizer",
    "NameNormalizer",
    "OrcidNormalizer",
    "TextNormalizer",
    "TitleNormalizer",
]