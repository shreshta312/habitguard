import sqlite3
import os
from pathlib import Path
from app.core.config import DB_PATH

def get_db_connection(db_path: Path = None) -> sqlite3.Connection:
    """
    Returns an active SQLite connection with WAL mode and foreign keys enabled.
    """
    if db_path is None:
        from app.core.config import DB_PATH
        target_path = DB_PATH
    else:
        target_path = db_path

    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn
