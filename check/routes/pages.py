import csv as _csv
import io as _io
import json as _json
import os as _os
from flask import Blueprint, render_template, current_app, abort, redirect, url_for, request
from ..equipment import list_equipments, get_equipment, EquipmentError
from ..csv_loader import load_checklist, ChecklistError
from ..database import (
    list_inspections, get_inspection_detail, count_inspections_on_date,
    get_latest_meter_readings,
)
from ..numfmt import fmt_num
from ._helpers import today_str

pages_bp = Blueprint("pages", __name__)

# 画面表示用の数値整形（小数最大3桁）。テンプレートで {{ x|num }} として使う。
pages_bp.app_template_filter("num")(fmt_num)

def _eqdir():
    return current_app.config["EQUIPMENTS_DIR"]

def _db():
    return current_app.config["DB_PATH"]

def _test_mode():
    """config.json の checklist_test_mode を毎回読む。true なら 1日1回ロックを解除。
    （ファイルが無い・壊れている・キーが無い場合は False＝本番どおり）"""
    path = current_app.config.get("CONFIG_JSON", "config.json")
    try:
        if _os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return bool(_json.load(f).get("checklist_test_mode", False))
    except Exception:
        pass
    return False

def _load_inspectors():
    path = current_app.config.get("INSPECTORS_CSV", "inspectors.csv")
    try:
        # Excel の「CSV UTF-8」は utf-8-sig、ふつうの「CSV」は cp932 なので両方試す
        with open(path, "rb") as f:
            data = f.read()
        text = None
        for enc in ("utf-8-sig", "cp932"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            return []
        rows = list(_csv.reader(_io.StringIO(text, newline="")))
        names = []
        for i, row in enumerate(rows):
            if not row:
                continue
            name = row[0].strip()
            # 1行目がヘッダ（氏名・名前・点検者）なら読み飛ばす
            if i == 0 and name in ("氏名", "名前", "点検者"):
                continue
            if name:
                names.append(name)
        return names
    except FileNotFoundError:
        return []

@pages_bp.route("/")
def index():
    eqs = list_equipments(_eqdir())
    if eqs:
        return redirect(url_for("pages.record", key=eqs[0]["key"]))
    return render_template("record.html", equipments=[], current=None,
                           sections=[], today=today_str(), error=None, mode="record",
                           meter_prev={}, test_mode=False)

@pages_bp.route("/record/<key>")
def record(key):
    eqs = list_equipments(_eqdir())
    try:
        cur = get_equipment(key, _eqdir())
    except EquipmentError:
        abort(404)
    error, sections = None, []
    try:
        items = load_checklist(cur["csv_path"])
        sections = _group_sections(items)
    except (ChecklistError, FileNotFoundError) as e:
        error = str(e)
    today = today_str()
    # 管理者が「編集可」にした過去点検の修正モード（?edit=<点検ID>）
    edit_iid = request.args.get("edit", type=int)
    edit_mode = False
    d = None
    if edit_iid:
        d = get_inspection_detail(edit_iid, db_path=_db())
        if d and d.get("equipment_key") == key and d.get("editable"):
            edit_mode = True
    # メータ項目の「前回指示値」を渡す（編集時はその点検より前の値を基準にする）
    if edit_mode and d:
        meter_prev = get_latest_meter_readings(key, before_date=d["inspection_date"],
                                               before_id=edit_iid, db_path=_db())
    else:
        meter_prev = get_latest_meter_readings(key, db_path=_db())
    test_mode = _test_mode()
    # テストモード中は 1日1回ロックを無効化（同じ日に何度でも保存できる）
    done_today = (not edit_mode) and (not test_mode) and count_inspections_on_date(key, today, db_path=_db()) > 0
    return render_template("record.html", equipments=eqs, current=cur,
                           sections=sections, today=today, error=error, mode="record",
                           inspectors=_load_inspectors(), done_today=done_today,
                           edit_iid=(edit_iid if edit_mode else None), meter_prev=meter_prev,
                           test_mode=test_mode)

@pages_bp.route("/history/<key>")
def history(key):
    eqs = list_equipments(_eqdir())
    try:
        cur = get_equipment(key, _eqdir())
    except EquipmentError:
        abort(404)
    rows = list_inspections(key, date_from=request.args.get("from"),
                            date_to=request.args.get("to"),
                            inspector=request.args.get("who"), db_path=_db())
    has_meter = False
    try:
        has_meter = any(it["item_type"] in ("meter", "meter_before", "meter_after")
                        for it in load_checklist(cur["csv_path"]))
    except (ChecklistError, FileNotFoundError):
        has_meter = False
    return render_template("history.html", equipments=eqs, current=cur, rows=rows,
                           mode="history", has_meter=has_meter)

@pages_bp.route("/detail/<int:iid>")
def detail(iid):
    d = get_inspection_detail(iid, db_path=_db())
    if d is None:
        abort(404)
    eqs = list_equipments(_eqdir())
    try:
        cur = get_equipment(d["equipment_key"], _eqdir())
    except EquipmentError:
        cur = None
    return render_template("detail.html", equipments=eqs, detail=d, current=cur, mode="detail")

def _group_sections(items):
    sections, order = {}, []
    for it in items:
        sec = it["section"] or "（未分類）"
        if sec not in sections:
            sections[sec] = []
            order.append(sec)
        sections[sec].append(it)
    return [(s, sections[s]) for s in order]
