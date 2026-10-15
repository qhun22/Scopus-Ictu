"""Thực hiện Alembic migration lên head cho database demo (đọc cấu hình từ backend_app.env)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from scripts import demo_launcher as dl

if __name__ == "__main__":
    sys.exit(dl.cmd_migrate(None))
