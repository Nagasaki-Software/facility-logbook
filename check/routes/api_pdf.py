import os
from datetime import date
from flask import Blueprint, current_app, abort, send_file, jsonify, request
from ..equipment import get_equipment, EquipmentError
from ..database import get_inspection_detail, list_inspections
from ..pdf_fill import fill_pdf, fill_pdf_multi

api_pdf_bp = Blueprint("api_pdf", __name__)


def _attach_meter_usage(detail, db_path=None):
    """その点検のメータ項目について、当日使用量＝使用後(value_number)−使用前(value_before)
    を計算し detail["meter_usage"] = {項目名: 使用量 or None} を付与する。
    未入力・要確認（使用後<使用前）は None（PDFでは空欄）。"""
    usage = {}
    for it in detail.get("items", []):
        if it.get("item_type") != "meter":
            continue
        after, before = it.get("value_number"), it.get("value_before")
        usage[it["item_name"]] = (after - before) if (
            after is not None and before is not None and after >= before) else None
    if usage:
        detail["meter_usage"] = usage


@api_pdf_bp.route("/api/inspections/<int:iid>/pdf")
def export_pdf(iid):
    detail = get_inspection_detail(iid, db_path=current_app.config["DB_PATH"])
    if detail is None:
        abort(404)
    _attach_meter_usage(detail, current_app.config["DB_PATH"])
    eqdir = current_app.config["EQUIPMENTS_DIR"]
    try:
        eq = get_equipment(detail["equipment_key"], eqdir)
    except EquipmentError:
        abort(404)
    out_dir = current_app.config["OUTPUT_DIR"]
    out_path = os.path.join(out_dir, f"inspection_{iid}.pdf")
    try:
        fill_pdf(eq["pdf_form_path"], eq["mapping_path"], detail, out_path)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 400
    return send_file(out_path, as_attachment=True,
                     download_name=f"{detail['equipment_key']}_{detail['inspection_date']}.pdf")


@api_pdf_bp.route("/api/inspections/bulk-pdf")
def bulk_pdf():
    key = request.args.get("key")
    if not key:
        return jsonify({"error": "key は必須です"}), 400
    date_from = request.args.get("from")
    date_to   = request.args.get("to")
    inspector = request.args.get("who")

    # ファイル名に使うため、期間は YYYY-MM-DD の日付だけを受け付ける
    for v in (date_from, date_to):
        if v:
            try:
                date.fromisoformat(v)
            except ValueError:
                return "<p style='font-family:sans-serif;padding:2em'>期間の日付は「2025-01-31」の形式で指定してください。<br><a href='javascript:history.back()'>戻る</a></p>", 400

    eqdir = current_app.config["EQUIPMENTS_DIR"]
    try:
        eq = get_equipment(key, eqdir)
    except EquipmentError:
        abort(404)

    rows = list_inspections(key, date_from=date_from, date_to=date_to,
                            inspector=inspector, db_path=current_app.config["DB_PATH"])
    if not rows:
        # HTML ページに戻ってエラーを表示するためリダイレクトせずテキストで返す
        return "<p style='font-family:sans-serif;padding:2em'>出力対象の点検データがありません。<br><a href='javascript:history.back()'>戻る</a></p>", 404

    details = [get_inspection_detail(r["id"], db_path=current_app.config["DB_PATH"]) for r in rows]
    details = [d for d in details if d is not None]
    for d in details:
        _attach_meter_usage(d, current_app.config["DB_PATH"])

    # ダウンロードファイル名の期間ラベル
    parts = []
    if date_from: parts.append(date_from)
    if date_to:   parts.append(date_to)
    date_label = "_".join(parts) if parts else "全期間"

    out_dir = current_app.config["OUTPUT_DIR"]
    out_path = os.path.join(out_dir, f"{key}_{date_label}_bulk.pdf")

    try:
        fill_pdf_multi(eq["pdf_form_path"], eq["mapping_path"], details, out_path)
    except (FileNotFoundError, ValueError) as e:
        return jsonify({"error": str(e)}), 400

    dl_name = f"{eq.get('name', key)}_{date_label}.pdf"
    return send_file(out_path, as_attachment=True, download_name=dl_name)
