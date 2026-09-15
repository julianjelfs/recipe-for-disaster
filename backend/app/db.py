"""SQLite connection and numbered-SQL migrations."""

import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def connect(path: Path | str) -> sqlite3.Connection:
    # FastAPI may run a sync dependency and its endpoint on different threadpool threads.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Apply migrations/NNN_*.sql files newer than PRAGMA user_version, each in its own transaction."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = int(path.name.split("_", 1)[0])
        if version <= current:
            continue
        conn.executescript(f"BEGIN;\n{path.read_text()}\nPRAGMA user_version = {version};\nCOMMIT;")
