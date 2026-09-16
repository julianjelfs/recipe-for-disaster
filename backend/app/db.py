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
    """Apply migrations/NNN_*.sql files newer than PRAGMA user_version, each in its own transaction.

    Foreign keys are off while a migration runs. SQLite can't drop NOT NULL or change a CHECK in
    place, so changing one means rebuilding the table, and dropping the old one would cascade to
    every ingredient, step and tag. `PRAGMA foreign_keys` is a no-op inside a transaction, which is
    why it is set here rather than in the migration. Afterwards the references are checked, so a
    migration that leaves the database inconsistent fails loudly instead of quietly.
    """
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = int(path.name.split("_", 1)[0])
        if version <= current:
            continue
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            conn.executescript(f"BEGIN;\n{path.read_text()}\nPRAGMA user_version = {version};\nCOMMIT;")
            broken = conn.execute("PRAGMA foreign_key_check").fetchall()
            if broken:
                raise RuntimeError(f"{path.name} left rows pointing at nothing: {[tuple(row) for row in broken[:5]]}")
        finally:
            conn.execute("PRAGMA foreign_keys = ON")
