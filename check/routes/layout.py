from flask import Blueprint, render_template, current_app, abort, request, jsonify, Response
from ..equipment import get_equipment, EquipmentError
from ..csv_loader import ChecklistError
from ..layout_fields import build_fields, save_layout, LayoutError
from .. import pdf_render

layout_bp = Blueprint("layout", __name__)

def _eq(key):
    return get_equipment(key, current_app.config["EQUIPMENTS_DIR"])

@layout_bp.route("/layout/<key>")
def editor(key):
    try:
        eq = _eq(key)
    except EquipmentError:
        abort(404)
    return render_template("layout.html", key=key, name=eq.get("name", key))

@layout_bp.route("/layout/<key>/page/<int:pno>.png")
def page_image(key, pno):
    try:
        eq = _eq(key)
    except EquipmentError:
        abort(404)
    try:
        res = pdf_render.render_page_png(eq["pdf_form_path"], pno)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"画像化に失敗しました: {e}"}), 400
    return Response(res["png"], mimetype="image/png")

@layout_bp.route("/api/layout/<key>/fields")
def fields(key):
    try:
        eq = _eq(key)
    except EquipmentError:
        abort(404)
    try:
        data = build_fields(eq)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ChecklistError as e:
        return jsonify({"error": str(e)}), 400
    try:
        data["pages"] = pdf_render.page_sizes(eq["pdf_form_path"])
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify(data)

@layout_bp.route("/api/layout/<key>", methods=["POST"])
def save(key):
    try:
        eq = _eq(key)
    except EquipmentError:
        abort(404)
    payload = request.get_json(silent=True) or {}
    try:
        sizes = pdf_render.page_sizes(eq["pdf_form_path"])
        page_sizes = {p["page"]: (p["w_pt"], p["h_pt"]) for p in sizes}
        save_layout(eq["mapping_path"], payload.get("fields", []),
                    payload.get("deletes", []), page_sizes)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except LayoutError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True})
