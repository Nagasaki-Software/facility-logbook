import os
import sqlite3
from datetime import datetime

DB_PATH = "records.db"

def get_connection(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(db_path=DB_PATH, schema_path="schema.sql"):
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = f.read()
    conn = get_connection(db_path)
    conn.executescript(schema)
    _migrate_inspections_editable(conn)
    conn.commit()
    conn.close()

def _migrate_inspections_editable(conn):
    """既存DBに editable 列を追加（非破壊）。既定0＝編集不可。"""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(inspections)").fetchall()]
    if "editable" not in cols:
        conn.execute("ALTER TABLE inspections ADD COLUMN editable INTEGER NOT NULL DEFAULT 0")
    # 積算メータの「使用前」値・時刻などの文字列値を保存する列（非破壊追加）
    icols = [r[1] for r in conn.execute("PRAGMA table_info(inspection_items)").fetchall()]
    if "value_before" not in icols:
        conn.execute("ALTER TABLE inspection_items ADD COLUMN value_before REAL")
    if "value_text" not in icols:
        conn.execute("ALTER TABLE inspection_items ADD COLUMN value_text TEXT")
    if "meter_group" not in icols:
        conn.execute("ALTER TABLE inspection_items ADD COLUMN meter_group TEXT")

def save_inspection(data, db_path=DB_PATH):
    conn = get_connection(db_path)
    try:
        with conn:
            now = datetime.now().isoformat(timespec="seconds")
            cur = conn.execute(
                "INSERT INTO inspections (equipment_key, inspection_date, inspector, note, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (data["equipment_key"], data["inspection_date"],
                 data.get("inspector", ""), data.get("note", ""), now),
            )
            iid = cur.lastrowid
            for it in data.get("items", []):
                conn.execute(
                    "INSERT INTO inspection_items (inspection_id, section, item_name, item_type,"
                    " unit, min_value, max_value, value_check, value_number, value_before, value_text, meter_group, judgement, sort_order, remark)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (iid, it.get("section", ""), it["item_name"], it["item_type"],
                     it.get("unit", ""), it.get("min_value"), it.get("max_value"),
                     it.get("value_check"), it.get("value_number"), it.get("value_before"), it.get("value_text"),
                     it.get("meter_group"), it.get("judgement", ""), it.get("sort_order", 0), it.get("remark", "")),
                )
        return iid
    finally:
        conn.close()

def list_inspections(equipment_key, date_from=None, date_to=None, inspector=None, db_path=DB_PATH):
    conn = get_connection(db_path)
    try:
        q = ("SELECT i.*, "
             "(SELECT COUNT(*) FROM inspection_items it WHERE it.inspection_id=i.id AND it.judgement='NG') AS ng_count "
             "FROM inspections i WHERE i.equipment_key=?")
        args = [equipment_key]
        if date_from:
            q += " AND i.inspection_date>=?"; args.append(date_from)
        if date_to:
            q += " AND i.inspection_date<=?"; args.append(date_to)
        if inspector:
            q += " AND i.inspector LIKE ?"; args.append(f"%{inspector}%")
        q += " ORDER BY i.inspection_date DESC, i.id DESC"
        rows = conn.execute(q, args).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def count_inspections_on_date(equipment_key, inspection_date, db_path=DB_PATH):
    """指定日に確定保存された点検の件数を返す（本日分済み判定用）"""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM inspections WHERE equipment_key=? AND inspection_date=?",
            (equipment_key, inspection_date)
        ).fetchone()
        return row["n"] if row else 0
    finally:
        conn.close()

def save_temp_inspection(equipment_key, payload_json, db_path=DB_PATH):
    """一時保存データを保存（設備ごとに1件・上書き）"""
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO temp_inspections(equipment_key, saved_at, data) VALUES(?,?,?)"
                " ON CONFLICT(equipment_key) DO UPDATE SET saved_at=excluded.saved_at, data=excluded.data",
                (equipment_key, now, payload_json)
            )
    finally:
        conn.close()

def load_temp_inspection(equipment_key, db_path=DB_PATH):
    """一時保存データを取得。なければ None を返す。"""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT saved_at, data FROM temp_inspections WHERE equipment_key=?",
            (equipment_key,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def clear_temp_inspection(equipment_key, db_path=DB_PATH):
    """一時保存データを削除する。"""
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM temp_inspections WHERE equipment_key=?", (equipment_key,))
    finally:
        conn.close()

def set_inspection_editable(inspection_id, value, db_path=DB_PATH):
    """点検を編集可(1)/不可(0)にする（管理者の解除・保存後の再ロック用）。"""
    conn = get_connection(db_path)
    try:
        with conn:
            cur = conn.execute(
                "UPDATE inspections SET editable=? WHERE id=?", (int(value), inspection_id)
            )
        return cur.rowcount > 0
    finally:
        conn.close()

def is_inspection_editable(inspection_id, db_path=DB_PATH):
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT editable FROM inspections WHERE id=?", (inspection_id,)
        ).fetchone()
        return bool(row and row["editable"])
    finally:
        conn.close()

def update_inspection(inspection_id, data, db_path=DB_PATH):
    """既存の点検を上書き更新する（ヘッダ＋明細を入れ替え）。成功で editable を0へ戻す。"""
    conn = get_connection(db_path)
    try:
        with conn:
            now = datetime.now().isoformat(timespec="seconds")
            cur = conn.execute(
                "UPDATE inspections SET inspection_date=?, inspector=?, note=?, updated_at=?, editable=0"
                " WHERE id=?",
                (data["inspection_date"], data.get("inspector", ""), data.get("note", ""),
                 now, inspection_id),
            )
            if cur.rowcount == 0:
                return False
            # 明細は入れ替え（既存削除→再挿入）
            conn.execute("DELETE FROM inspection_items WHERE inspection_id=?", (inspection_id,))
            for it in data.get("items", []):
                conn.execute(
                    "INSERT INTO inspection_items (inspection_id, section, item_name, item_type,"
                    " unit, min_value, max_value, value_check, value_number, value_before, value_text, meter_group, judgement, sort_order, remark)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (inspection_id, it.get("section", ""), it["item_name"], it["item_type"],
                     it.get("unit", ""), it.get("min_value"), it.get("max_value"),
                     it.get("value_check"), it.get("value_number"), it.get("value_before"), it.get("value_text"),
                     it.get("meter_group"), it.get("judgement", ""), it.get("sort_order", 0), it.get("remark", "")),
                )
        return True
    finally:
        conn.close()

def get_inspection_detail(inspection_id, db_path=DB_PATH):
    conn = get_connection(db_path)
    try:
        head = conn.execute("SELECT * FROM inspections WHERE id=?", (inspection_id,)).fetchone()
        if head is None:
            return None
        items = conn.execute(
            "SELECT * FROM inspection_items WHERE inspection_id=? ORDER BY sort_order",
            (inspection_id,),
        ).fetchall()
        d = dict(head)
        d["items"] = [dict(r) for r in items]
        return d
    finally:
        conn.close()

def get_latest_meter_readings(equipment_key, before_date=None, before_id=None, db_path=DB_PATH):
    """使用前の自動入力用に『前回の使用後の値』を返す。
    - 1行方式(meter)       : {項目名: 前回の使用後(value_number)}
    - 行分け方式(meter_after): {'grp:'+メータ組: 前回の使用後(value_number)}
    before_date/before_id を渡すと、その点検より前の最新値を返す（過去点検の編集時用）。"""
    conn = get_connection(db_path)
    try:
        q = ("SELECT it.item_type AS t, it.item_name AS name, it.meter_group AS grp, "
             " it.value_number AS val, i.inspection_date AS d, i.id AS iid "
             "FROM inspection_items it JOIN inspections i ON it.inspection_id=i.id "
             "WHERE i.equipment_key=? AND it.value_number IS NOT NULL "
             " AND it.item_type IN ('meter','meter_after')")
        args = [equipment_key]
        if before_date is not None and before_id is not None:
            q += " AND (i.inspection_date < ? OR (i.inspection_date = ? AND i.id < ?))"
            args += [before_date, before_date, before_id]
        q += " ORDER BY i.inspection_date DESC, i.id DESC"
        rows = conn.execute(q, args).fetchall()
        latest = {}
        for r in rows:
            key = r["name"] if r["t"] == "meter" else ("grp:" + (r["grp"] or ""))
            if key not in latest:   # 降順なので最初に出たものが最新
                latest[key] = r["val"]
        return latest
    finally:
        conn.close()

def _usage_row(date, inspector, name, unit, before, after):
    if before is None or after is None:
        usage, status = "", "未入力"
    elif after < before:
        usage, status = "", "要確認"
    else:
        usage, status = after - before, "正常"
    return {"date": date, "inspector": inspector, "name": name, "unit": unit,
            "before": ("" if before is None else before),
            "after": ("" if after is None else after),
            "usage": usage, "status": status}


def meter_usage_rows(equipment_key, date_from=None, date_to=None, db_path=DB_PATH):
    """当日使用量＝使用後−使用前。1行方式(meter)と行分け方式(meter_before/after)の両対応。
    両方そろっていなければ『未入力』、使用後<使用前なら『要確認』として使用量は空にする。"""
    conn = get_connection(db_path)
    try:
        q = ("SELECT i.id AS iid, i.inspection_date AS date, i.inspector AS inspector, "
             " it.item_type AS t, it.item_name AS name, it.meter_group AS grp, "
             " it.value_number AS vnum, it.value_before AS vbefore, it.unit AS unit "
             "FROM inspection_items it JOIN inspections i ON it.inspection_id=i.id "
             "WHERE i.equipment_key=? AND it.item_type IN ('meter','meter_before','meter_after')")
        args = [equipment_key]
        if date_from:
            q += " AND i.inspection_date>=?"; args.append(date_from)
        if date_to:
            q += " AND i.inspection_date<=?"; args.append(date_to)
        q += " ORDER BY i.inspection_date, i.id"
        rows = conn.execute(q, args).fetchall()
    finally:
        conn.close()

    out = []
    pairs = {}  # (点検ID, メータ組) -> 集約
    for r in rows:
        if r["t"] == "meter":
            out.append(_usage_row(r["date"], r["inspector"], r["name"], r["unit"] or "",
                                  r["vbefore"], r["vnum"]))
        else:
            key = (r["iid"], r["grp"] or "")
            p = pairs.setdefault(key, {"before": None, "after": None, "unit": "",
                                       "name": (r["grp"] or r["name"]), "date": r["date"],
                                       "inspector": r["inspector"]})
            if r["t"] == "meter_before":
                p["before"] = r["vnum"]
            else:
                p["after"] = r["vnum"]
            if r["unit"]:
                p["unit"] = r["unit"]
    for p in pairs.values():
        out.append(_usage_row(p["date"], p["inspector"], p["name"], p["unit"],
                              p["before"], p["after"]))
    out.sort(key=lambda x: (x["date"], x["name"]))
    return out
