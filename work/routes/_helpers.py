"""Shared utilities for route blueprints."""
import sqlite3


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    """Convert a sqlite3.Row to a plain dict, or None to None."""
    return None if row is None else {k: row[k] for k in row.keys()}
