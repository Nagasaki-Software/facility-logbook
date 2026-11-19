from flask import Blueprint, g, jsonify, request, abort
from ..models import buttons as B
from ._helpers import row_to_dict

bp = Blueprint("api_buttons", __name__, url_prefix="/api")


@bp.get("/button_groups")
def list_groups():
    return jsonify({"groups": [row_to_dict(r) for r in B.list_groups(g.db)]})


@bp.post("/button_groups")
def create_group():
    name = (request.get_json(silent=True) or {}).get("name", "")
    gid = B.create_group(g.db, name=name)
    return jsonify({"id": gid, "name": name}), 201


@bp.patch("/button_groups/<int:gid>")
def rename_group(gid):
    name = (request.get_json(silent=True) or {}).get("name", "")
    if not B.rename_group(g.db, gid, name=name):
        abort(404)
    return jsonify({"id": gid, "name": name})


@bp.delete("/button_groups/<int:gid>")
def delete_group(gid):
    B.delete_group(g.db, gid)
    return "", 204


@bp.post("/button_groups/reorder")
def reorder_groups():
    ids = (request.get_json(silent=True) or {}).get("ordered_ids", [])
    B.reorder_group(g.db, ids)
    return jsonify({"ok": True})


@bp.get("/button_groups/<int:gid>/buttons")
def list_buttons(gid):
    return jsonify({"buttons": [row_to_dict(r) for r in B.list_buttons(g.db, gid)]})


@bp.post("/buttons")
def create_button():
    data = request.get_json(silent=True) or {}
    group_id = data.get("group_id")
    if not group_id:
        abort(400, "group_id required")
    label = data.get("label", "")
    bid = B.create_button(g.db, group_id=group_id, label=label)
    return jsonify({"id": bid, "label": label}), 201


@bp.patch("/buttons/<int:bid>")
def rename_button(bid):
    label = (request.get_json(silent=True) or {}).get("label", "")
    if not B.rename_button(g.db, bid, label=label):
        abort(404)
    return jsonify({"id": bid, "label": label})


@bp.delete("/buttons/<int:bid>")
def delete_button(bid):
    B.delete_button(g.db, bid)
    return "", 204


@bp.patch("/buttons/<int:bid>/pin")
def pin_button(bid):
    pinned = bool((request.get_json(silent=True) or {}).get("pinned", False))
    if not B.set_button_pinned(g.db, bid, pinned=pinned):
        abort(404)
    return jsonify({"ok": True})


@bp.post("/button_groups/<int:gid>/buttons/reorder")
def reorder_buttons(gid):
    ids = (request.get_json(silent=True) or {}).get("ordered_ids", [])
    B.reorder_buttons(g.db, gid, ids)
    return jsonify({"ok": True})
