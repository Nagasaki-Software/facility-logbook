import csv as _csv
import io
import json
import math
from flask import Blueprint, request, jsonify, current_app, Response
from ..equipment import get_equipment, EquipmentError
from ..csv_loader import load_checklist, judge, ChecklistError
from ..database import (
    save_inspection, save_temp_inspection, load_temp_inspection, clear_temp_inspection,
    get_inspection_detail, update_inspection, is_inspection_editable, meter_usage_rows,
    count_inspections_on_date,
)
from ..numfmt import fmt_num
from .pages import _test_mode
from datetime import date as _date
import audit_log

api_inspections_bp = Blueprint("api_inspections", __name__)


def _alog(action, target="", detail=""):
    audit_log.write_log(request.remote_addr, "点検", action, target, detail)


class _ItemError(ValueError):
    pass


def _parse_num(num, item_name, label):
    """数値入力を float に変換。空は None。数値以外・無効値は _ItemError。"""
    if num is None or num == "":
        return None
    try:
        val = float(num)
    except (TypeError, ValueError):
        raise _ItemError(f"'{item_name}' の{label}に数値以外が入力されました: {num!r}")
    if math.isnan(val) or math.isinf(val):
        raise _ItemError(f"'{item_name}' の{label}に無効な数値が入力されました: {num!r}")
    return val


def _build_items(items_def, values):
    """チェックリスト定義＋入力値から、保存用の明細リストを組み立てる。
    数値以外などの不正入力は _ItemError を送出する。"""
    items = []
    for d in items_def:
        name = d["item_name"]
        v = values.get(name, {})
        value_check, value_number, value_before, value_text, judgement = None, None, None, None, ""
        if d["item_type"] == "check":
            # 新形式 result('OK'/'NG'/'')。旧形式 check(true/false) も受け付ける。
            result = v.get("result")
            if result is None:
                result = "OK" if v.get("check") is True else ""
            value_check = 1 if result == "OK" else 0
            judgement = result if result in ("OK", "NG") else ""
        elif d["item_type"] == "meter":
            # 累計メータ（1行方式）：使用前(before)・使用後(after) を保存。合否は付けない。
            value_before = _parse_num(v.get("before"), name, "使用前")
            value_number = _parse_num(v.get("after"), name, "使用後")
        elif d["item_type"] in ("meter_before", "meter_after"):
            # 累計メータ（行分け方式）：各行の読み値を value_number に保存。組は meter_group で対応付け。
            value_number = _parse_num(v.get("number"), name, name)
        elif d["item_type"] == "time":
            # 時刻入力（HH:MM）。文字列として保存。合否は付けない。
            t = (v.get("time") or "").strip()
            value_text = t or None
        else:
            value_number = _parse_num(v.get("number"), name, name)
            if value_number is not None:
                judgement = judge(value_number, d["min_value"], d["max_value"])
        items.append({
            "section": d["section"], "item_name": name, "item_type": d["item_type"],
            "unit": d["unit"], "min_value": d["min_value"], "max_value": d["max_value"],
            "value_check": value_check, "value_number": value_number, "value_before": value_before,
            "value_text": value_text, "meter_group": d.get("meter_group", ""),
            "judgement": judgement, "sort_order": d["sort_order"], "remark": d["remark"],
        })
    return items


def _load_items_def(key):
    """設備のチェックリスト定義を読む。(items_def, error_response) を返す。"""
    eqdir = current_app.config["EQUIPMENTS_DIR"]
    try:
        eq = get_equipment(key, eqdir)
        return load_checklist(eq["csv_path"]), None
    except EquipmentError:
        return None, (jsonify({"error": "設備が見つかりません"}), 404)
    except (ChecklistError, FileNotFoundError) as e:
        return None, (jsonify({"error": str(e)}), 400)


def _valid_date(s):
    """YYYY-MM-DD 形式の実在する日付なら True。"""
    if not isinstance(s, str) or len(s) != 10:
        return False
    try:
        _date.fromisoformat(s)
        return True
    except ValueError:
        return False


@api_inspections_bp.route("/api/inspections", methods=["POST"])
def create_inspection():
    data = request.get_json(silent=True) or {}
    key = data.get("equipment_key")
    if not key:
        return jsonify({"error": "equipment_key は必須です"}), 400
    idate = data.get("inspection_date") or ""
    if not _valid_date(idate):
        return jsonify({"error": "点検日が正しくありません（例：2026-01-31 の形で入力してください）"}), 400
    # 1日1回ロック（画面だけでなくサーバ側でも確認）。テストモード中は解除。
    if not _test_mode() and count_inspections_on_date(key, idate, db_path=current_app.config["DB_PATH"]) > 0:
        return jsonify({"error": f"この設備の {idate} の点検は既に保存されています。"}), 409
    items_def, err = _load_items_def(key)
    if err:
        return err
    try:
        items = _build_items(items_def, data.get("values", {}))
    except _ItemError as e:
        return jsonify({"error": str(e)}), 400

    record = {
        "equipment_key": key,
        "inspection_date": idate,
        "inspector": data.get("inspector", ""),
        "note": data.get("note", ""),
        "items": items,
    }
    iid = save_inspection(record, db_path=current_app.config["DB_PATH"])
    # 本保存が成功したら一時保存を削除
    clear_temp_inspection(key, db_path=current_app.config["DB_PATH"])
    _alog("点検保存", f"点検ID {iid}", f"{key} / {record['inspection_date']} / {record['inspector']}")
    return jsonify({"id": iid})


@api_inspections_bp.route("/api/inspections/<int:iid>", methods=["GET"])
def get_inspection(iid):
    # 編集モードのプリフィル用。明細と editable フラグを含む。
    detail = get_inspection_detail(iid, db_path=current_app.config["DB_PATH"])
    if detail is None:
        return jsonify({"error": "点検が見つかりません"}), 404
    return jsonify(detail)


@api_inspections_bp.route("/api/inspections/<int:iid>", methods=["PUT"])
def overwrite_inspection(iid):
    # 管理者が「編集可」にした点検だけ上書き更新できる（保存後は自動で再ロック）。
    detail = get_inspection_detail(iid, db_path=current_app.config["DB_PATH"])
    if detail is None:
        return jsonify({"error": "点検が見つかりません"}), 404
    if not is_inspection_editable(iid, db_path=current_app.config["DB_PATH"]):
        return jsonify({"error": "この点検は編集可になっていません（管理者の解除が必要です）"}), 403

    data = request.get_json(silent=True) or {}
    if "inspection_date" in data and not _valid_date(data["inspection_date"]):
        return jsonify({"error": "点検日が正しくありません（例：2026-01-31 の形で入力してください）"}), 400
    items_def, err = _load_items_def(detail["equipment_key"])
    if err:
        return err
    try:
        items = _build_items(items_def, data.get("values", {}))
    except _ItemError as e:
        return jsonify({"error": str(e)}), 400

    record = {
        "inspection_date": data.get("inspection_date", detail["inspection_date"]),
        "inspector": data.get("inspector", ""),
        "note": data.get("note", ""),
        "items": items,
    }
    ok = update_inspection(iid, record, db_path=current_app.config["DB_PATH"])
    if not ok:
        return jsonify({"error": "更新に失敗しました"}), 400
    _alog("点検上書き(管理者編集)", f"点検ID {iid}", f"{record['inspection_date']} / {record['inspector']}")
    return jsonify({"id": iid})


# ── 一時保存 API ──────────────────────────────────────────

@api_inspections_bp.route("/api/temp/<key>", methods=["GET"])
def get_temp(key):
    result = load_temp_inspection(key, db_path=current_app.config["DB_PATH"])
    if result is None:
        return jsonify(None)
    result["data"] = json.loads(result["data"])
    return jsonify(result)

@api_inspections_bp.route("/api/temp/<key>", methods=["PUT"])
def put_temp(key):
    body = request.get_json(force=True) or {}
    save_temp_inspection(key, json.dumps(body, ensure_ascii=False),
                         db_path=current_app.config["DB_PATH"])
    return jsonify({"ok": True})

@api_inspections_bp.route("/api/temp/<key>", methods=["DELETE"])
def delete_temp(key):
    clear_temp_inspection(key, db_path=current_app.config["DB_PATH"])
    return jsonify({"ok": True})


# ── 水使用量CSV出力 ────────────────────────────────────────

def _fmt_csvnum(v):
    """CSV用の数値整形。空はそのまま、数値は fmt_num（小数最大3桁）で整形。"""
    if v == "" or v is None:
        return ""
    return fmt_num(v)


@api_inspections_bp.route("/api/inspections/usage-csv", methods=["GET"])
def usage_csv():
    key = request.args.get("key")
    if not key:
        return jsonify({"error": "key は必須です"}), 400
    rows = meter_usage_rows(key, request.args.get("from"), request.args.get("to"),
                            db_path=current_app.config["DB_PATH"])
    buf = io.StringIO()
    w = _csv.writer(buf)
    w.writerow(["点検日", "点検者", "項目名", "使用前", "使用後", "当日使用量", "単位", "状態"])
    for r in rows:
        w.writerow([r["date"], r["inspector"], r["name"],
                    _fmt_csvnum(r["before"]), _fmt_csvnum(r["after"]),
                    _fmt_csvnum(r["usage"]), r["unit"], r["status"]])
    body = "﻿" + buf.getvalue()   # ExcelでもUTF-8と分かるようBOMを付ける
    fname = f"meter_usage_{key}.csv"
    return Response(body, mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={fname}"})
