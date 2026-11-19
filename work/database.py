import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | str) -> None:
    ddl = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_connection(db_path)
    try:
        conn.executescript(ddl)
        _migrate_entries_sort_order(conn)
        _migrate_records_finalized(conn)
        conn.commit()
    finally:
        conn.close()


def _migrate_entries_sort_order(conn: sqlite3.Connection) -> None:
    # Add the sort_order column to pre-existing databases (non-destructive),
    # then seed it from id so the current display order is preserved.
    cols = [r[1] for r in conn.execute("PRAGMA table_info(entries)").fetchall()]
    if "sort_order" not in cols:
        conn.execute("ALTER TABLE entries ADD COLUMN sort_order REAL NOT NULL DEFAULT 0")
        conn.execute("UPDATE entries SET sort_order = id")


def _migrate_records_finalized(conn: sqlite3.Connection) -> None:
    # Add the finalized column to pre-existing databases (non-destructive).
    # Existing records default to 0 (editable / not yet confirmed).
    cols = [r[1] for r in conn.execute("PRAGMA table_info(records)").fetchall()]
    if "finalized" not in cols:
        conn.execute("ALTER TABLE records ADD COLUMN finalized INTEGER NOT NULL DEFAULT 0")
