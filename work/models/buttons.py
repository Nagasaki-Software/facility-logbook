import sqlite3


def _next_sort_order(conn: sqlite3.Connection, table: str, where: str = "", params=()) -> int:
    sql = f"SELECT COALESCE(MAX(sort_order), -1) + 1 FROM {table}"
    if where:
        sql += " WHERE " + where
    return conn.execute(sql, params).fetchone()[0]


def create_group(conn: sqlite3.Connection, *, name: str) -> int:
    so = _next_sort_order(conn, "button_groups")
    cur = conn.execute(
        "INSERT INTO button_groups (name, sort_order) VALUES (?, ?)", (name, so)
    )
    conn.commit()
    return cur.lastrowid


def rename_group(conn: sqlite3.Connection, group_id: int, *, name: str) -> bool:
    cur = conn.execute(
        "UPDATE button_groups SET name = ? WHERE id = ?", (name, group_id)
    )
    conn.commit()
    return cur.rowcount > 0


def delete_group(conn: sqlite3.Connection, group_id: int) -> bool:
    cur = conn.execute("DELETE FROM button_groups WHERE id = ?", (group_id,))
    conn.commit()
    return cur.rowcount > 0


def list_groups(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM button_groups ORDER BY sort_order, id"
    ).fetchall())


def reorder_group(conn: sqlite3.Connection, ordered_ids: list[int]) -> None:
    for i, gid in enumerate(ordered_ids):
        conn.execute(
            "UPDATE button_groups SET sort_order = ? WHERE id = ?", (i, gid)
        )
    conn.commit()


def create_button(conn: sqlite3.Connection, *, group_id: int, label: str) -> int:
    so = _next_sort_order(conn, "buttons", "group_id = ?", (group_id,))
    cur = conn.execute(
        "INSERT INTO buttons (group_id, label, is_pinned, sort_order)"
        " VALUES (?, ?, 0, ?)",
        (group_id, label, so),
    )
    conn.commit()
    return cur.lastrowid


def rename_button(conn: sqlite3.Connection, button_id: int, *, label: str) -> bool:
    cur = conn.execute(
        "UPDATE buttons SET label = ? WHERE id = ?", (label, button_id)
    )
    conn.commit()
    return cur.rowcount > 0


def delete_button(conn: sqlite3.Connection, button_id: int) -> bool:
    cur = conn.execute("DELETE FROM buttons WHERE id = ?", (button_id,))
    conn.commit()
    return cur.rowcount > 0


def set_button_pinned(conn: sqlite3.Connection, button_id: int, *, pinned: bool) -> bool:
    cur = conn.execute(
        "UPDATE buttons SET is_pinned = ? WHERE id = ?",
        (1 if pinned else 0, button_id),
    )
    conn.commit()
    return cur.rowcount > 0


def list_buttons(conn: sqlite3.Connection, group_id: int) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM buttons WHERE group_id = ?"
        " ORDER BY is_pinned DESC, sort_order ASC, id ASC",
        (group_id,),
    ).fetchall())


def reorder_buttons(
    conn: sqlite3.Connection, group_id: int, ordered_ids: list[int]
) -> None:
    for i, bid in enumerate(ordered_ids):
        conn.execute(
            "UPDATE buttons SET sort_order = ? WHERE id = ? AND group_id = ?",
            (i, bid, group_id),
        )
    conn.commit()
