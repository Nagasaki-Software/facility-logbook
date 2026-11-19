import sqlite3
from datetime import datetime


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def list_progress(
    conn: sqlite3.Connection, record_id: int, manual_file: str
) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM manual_progress WHERE record_id = ? AND manual_file = ?",
        (record_id, manual_file),
    ).fetchall())


def mark_done(
    conn: sqlite3.Connection, record_id: int, *,
    manual_file: str, step_key: str, done_time: str, entry_id: int | None,
) -> None:
    # 同じ手順を2回目以降に押したときは、実施時刻と記録行IDを最新に更新する
    conn.execute(
        "INSERT INTO manual_progress"
        " (record_id, manual_file, step_key, done_time, entry_id, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?)"
        " ON CONFLICT(record_id, manual_file, step_key) DO UPDATE SET"
        " done_time = excluded.done_time,"
        " entry_id = excluded.entry_id,"
        " updated_at = excluded.updated_at",
        (record_id, manual_file, step_key, done_time, entry_id, _now()),
    )
    conn.commit()


def clear_step(
    conn: sqlite3.Connection, record_id: int, *, manual_file: str, step_key: str
) -> bool:
    cur = conn.execute(
        "DELETE FROM manual_progress"
        " WHERE record_id = ? AND manual_file = ? AND step_key = ?",
        (record_id, manual_file, step_key),
    )
    conn.commit()
    return cur.rowcount > 0


def clear_manual(
    conn: sqlite3.Connection, record_id: int, *, manual_file: str
) -> int:
    cur = conn.execute(
        "DELETE FROM manual_progress WHERE record_id = ? AND manual_file = ?",
        (record_id, manual_file),
    )
    conn.commit()
    return cur.rowcount
