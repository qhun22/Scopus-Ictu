"""Root conftest — loads .env before test isolation guard fires.

The tests/conftest.py guard checks os.environ for TEST_DATABASE_URL at
import time. Pydantic-settings reads .env but does not inject into
os.environ. This root conftest loads .env into os.environ via dotenv
so the guard sees TEST_DATABASE_URL.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=False)
