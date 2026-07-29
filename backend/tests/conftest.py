import os
import tempfile
import pytest
from pathlib import Path

# Configure isolated DB path BEFORE any app imports happen
_temp_dir = tempfile.mkdtemp(prefix="hg_test_db_")
_test_db_path = Path(_temp_dir) / "isolated_test_habitguard.db"
os.environ["HABITGUARD_DB_PATH"] = str(_test_db_path)

import app.core.config as config
config.DB_PATH = _test_db_path

from app.db.migrations import run_migrations
run_migrations(_test_db_path)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db_session():
    """Ensure test session executes against isolated temp SQLite database."""
    yield _test_db_path
    try:
        if _test_db_path.exists():
            _test_db_path.unlink(missing_ok=True)
    except Exception:
        pass
