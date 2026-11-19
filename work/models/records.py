import sqlite3
from datetime import datetime


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create_record(conn: sqlite3.Connection, *, title: str, record_date: str) -> int:
    cur = conn.execute(
        "INSERT INTO records (title, record_date, created_at) VALUES (?, ?, ?)",
        (title, record_date, _now()),
    )
    conn.commit()
    return cur.lastrowid


def get_record(conn: sqlite3.Connection, record_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM records WHERE id = ?", (record_id,)
    ).fetchone()


def get_current_record(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM records ORDER BY created_at DESC, id DESC LIMIT 1"
    ).fetchone()


def update_record_header(
    conn: sqlite3.Connection, record_id: int, *, title: str, record_date: str
) -> bool:
    cur = conn.execute(
        "UPDATE records SET title = ?, record_date = ? WHERE id = ?",
        (title, record_date, record_id),
    )
    conn.commit()
    return cur.rowcount > 0


def set_finalized(conn: sqlite3.Connection, record_id: int, value: int) -> bool:
    cur = conn.execute(
        "UPDATE records SET finalized = ? WHERE id = ?", (int(value), record_id)
    )
    conn.commit()
    return cur.rowcount > 0


def is_finalized(conn: sqlite3.Connection, record_id: int) -> bool:
    row = conn.execute(
        "SELECT finalized FROM records WHERE id = ?", (record_id,)
    ).fetchone()
    return bool(row and row["finalized"])


def delete_record(conn: sqlite3.Connection, record_id: int) -> bool:
    # entries は ON DELETE CASCADE で一緒に削除される（FK 有効時）
    cur = conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
    conn.commit()
    return cur.rowcount > 0


def _sort_order_for(
    conn: sqlite3.Connection, record_id: int, after_id: int | None
) -> float:
    # after_id semantics:
    #   None -> append at the end
    #   0    -> insert at the very top
    #   N    -> insert right after entry N (between it and the next row)
    if after_id is None:
        row = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM entries WHERE record_id = ?",
            (record_id,),
        ).fetchone()
        return row[0]
    if after_id == 0:
        row = conn.execute(
            "SELECT MIN(sort_order) FROM entries WHERE record_id = ?", (record_id,)
        ).fetchone()
        return (row[0] - 1) if row[0] is not None else 1
    after = conn.execute(
        "SELECT sort_order FROM entries WHERE id = ? AND record_id = ?",
        (after_id, record_id),
    ).fetchone()
    if after is None:
        row = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM entries WHERE record_id = ?",
            (record_id,),
        ).fetchone()
        return row[0]
    after_so = after[0]
    nxt = conn.execute(
        "SELECT MIN(sort_order) FROM entries WHERE record_id = ? AND sort_order > ?",
        (record_id, after_so),
    ).fetchone()
    if nxt[0] is None:
        return after_so + 1
    return (after_so + nxt[0]) / 2.0


def add_entry(
    conn: sqlite3.Connection, record_id: int, *, time_text: str, content: str,
    after_id: int | None = None,
) -> int:
    sort_order = _sort_order_for(conn, record_id, after_id)
    cur = conn.execute(
        "INSERT INTO entries (record_id, time_text, content, is_important, sort_order, created_at)"
        " VALUES (?, ?, ?, 0, ?, ?)",
        (record_id, time_text, content, sort_order, _now()),
    )
    conn.commit()
    return cur.lastrowid


def update_entry(
    conn: sqlite3.Connection, entry_id: int, *, time_text: str, content: str
) -> bool:
    cur = conn.execute(
        "UPDATE entries SET time_text = ?, content = ?, updated_at = ? WHERE id = ?",
        (time_text, content, _now(), entry_id),
    )
    conn.commit()
    return cur.rowcount > 0


def set_entry_important(
    conn: sqlite3.Connection, entry_id: int, *, level: int
) -> bool:
    # level: 0=なし(白) / 1=黄 / 2=ピンク
    cur = conn.execute(
        "UPDATE entries SET is_important = ? WHERE id = ?",
        (int(level), entry_id),
    )
    conn.commit()
    return cur.rowcount > 0


def delete_entry(conn: sqlite3.Connection, entry_id: int) -> bool:
    cur = conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    conn.commit()
    return cur.rowcount > 0


def set_entries_order(
    conn: sqlite3.Connection, record_id: int, ordered_ids: list[int]
) -> None:
    # 渡された順に sort_order を振り直す（その記録に属する行だけ更新）
    for i, eid in enumerate(ordered_ids):
        conn.execute(
            "UPDATE entries SET sort_order = ? WHERE id = ? AND record_id = ?",
            (i, eid, record_id),
        )
    conn.commit()


def get_entry(conn: sqlite3.Connection, entry_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM entries WHERE id = ?", (entry_id,)
    ).fetchone()


def list_entries(conn: sqlite3.Connection, record_id: int) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM entries WHERE record_id = ? ORDER BY sort_order ASC, id ASC",
        (record_id,),
    ).fetchall())


def count_record_photos(conn: sqlite3.Connection, record_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM record_photos WHERE record_id = ?", (record_id,)
    ).fetchone()[0]


def add_record_photo(
    conn: sqlite3.Connection, record_id: int, *,
    filename: str, original_name: str = "", memo: str = "",
) -> int:
    cur = conn.execute(
        "INSERT INTO record_photos (record_id, filename, original_name, memo, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (record_id, filename, original_name, memo, _now()),
    )
    conn.commit()
    return cur.lastrowid


def list_record_photos(conn: sqlite3.Connection, record_id: int) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM record_photos WHERE record_id = ? ORDER BY id ASC",
        (record_id,),
    ).fetchall())


def get_record_photo(conn: sqlite3.Connection, photo_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM record_photos WHERE id = ?", (photo_id,)
    ).fetchone()


def update_record_photo_memo(
    conn: sqlite3.Connection, photo_id: int, *, memo: str
) -> bool:
    cur = conn.execute(
        "UPDATE record_photos SET memo = ? WHERE id = ?", (memo, photo_id)
    )
    conn.commit()
    return cur.rowcount > 0


def delete_record_photo(conn: sqlite3.Connection, photo_id: int) -> bool:
    cur = conn.execute("DELETE FROM record_photos WHERE id = ?", (photo_id,))
    conn.commit()
    return cur.rowcount > 0


def list_records_in_month(
    conn: sqlite3.Connection, *, year: int, month: int
) -> list[sqlite3.Row]:
    prefix = f"{year:04d}-{month:02d}-"
    return list(conn.execute(
        "SELECT * FROM records WHERE record_date LIKE ? ORDER BY record_date, id",
        (prefix + "%",),
    ).fetchall())


def list_records_on_date(
    conn: sqlite3.Connection, record_date: str
) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM records WHERE record_date = ? ORDER BY created_at, id",
        (record_date,),
    ).fetchall())


def search_records(conn: sqlite3.Connection, q: str) -> list[sqlite3.Row]:
    # タイトル、または記録内の作業内容に q を含む記録を新しい順に返す
    like = f"%{q}%"
    return list(conn.execute(
        "SELECT DISTINCT r.* FROM records r"
        " LEFT JOIN entries e ON e.record_id = r.id"
        " WHERE r.title LIKE ? OR e.content LIKE ?"
        " ORDER BY r.record_date DESC, r.id DESC LIMIT 200",
        (like, like),
    ).fetchall())


def recent_contents(conn: sqlite3.Connection, limit: int = 40) -> list[str]:
    # よく使う／最近使った作業内容を、新しく使った順の重複なしで返す
    rows = conn.execute(
        "SELECT content FROM entries WHERE content <> ''"
        " GROUP BY content ORDER BY MAX(id) DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [r["content"] for r in rows]


def list_records_between(
    conn: sqlite3.Connection, *, start: str, end: str
) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM records WHERE record_date BETWEEN ? AND ?"
        " ORDER BY record_date, id",
        (start, end),
    ).fetchall())
