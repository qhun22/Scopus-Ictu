"""Logging configuration — M0 scaffold."""

from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger (M0 stub).

    TODO(M1): wire to app.core.config.settings.environment,
    add structured log handlers, and use JSON format for prod.
    """
    logging.basicConfig(
        level=level,
        stream=sys.stdout,
        format="%(asctime)s | %(name)-40s | %(levelname)-8s | %(message)s",
    )


# Module-level logger — imported by other app modules.
logger = logging.getLogger("scopus_ictu")
