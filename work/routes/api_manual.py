from flask import Blueprint, g, jsonify, request, abort

from ..manual_loader import ManualError, list_manuals, load_manual
from ..models import records as M
from ..models import manual_progress as P
from ._helpers import row_to_dict
import audit_log


def _alog(action, target="", detail=""):
    audit_log.write_log(request.remote_addr, "運転記録", action, target, detail)


bp = Blueprint("api_manual", __name__, url_prefix="/api")


def _require_not_finalized(record_id) -> None:
    """確定済みの記録には手順の実施を記録できない（既存の行追加と同じ扱い）。"""
    if M.is_finalized(g.db, record_id):
        abort(403, "確定済みの記録のため編集できません。修正は管理者へ依頼してください。")


def _progress_dict(record_id: int, manual_file: str) -> dict:
    return {
        r["step_key"]: {"done_time": r["done_time"], "entry_id": r["entry_id"]}
        for r in P.list_progress(g.db, record_id, manual_file)
    }


def _manual_arg() -> str:
    name = (request.args.get("manual") or "").strip()
    if not name:
        data = request.get_json(silent=True) or {}
        name = (data.get("manual") or "").strip()
    if not name:
        abort(400, "manual required")
    return name


@bp.get("/manuals")
def get_manuals():
    return jsonify({"manuals": list_manuals()})


@bp.get("/manual_steps")
def get_manual_steps():
    name = _manual_arg()
    try:
        steps = load_manual(name)
    except ManualError as e:
        # CSVの書き方の誤りは画面にそのまま出して直してもらう（アプリは落とさない）
        return jsonify({"error": str(e)}), 400
    return jsonify({"manual": name, "steps": steps})


@bp.get("/records/<int:rid>/manual_progress")
def get_manual_progress(rid):
    if not M.get_record(g.db, rid):
        abort(404)
    return jsonify({"progress": _progress_dict(rid, _manual_arg())})


@bp.post("/records/<int:rid>/manual_steps")
def do_manual_step(rid):
    """手順を1つ実施：運転記録に1行追加し、その手順を実施済みにする。"""
    if not M.get_record(g.db, rid):
        abort(404)
    _require_not_finalized(rid)
    data = request.get_json(silent=True) or {}
    name = _manual_arg()
    step_key = (data.get("step_key") or "").strip()
    time_text = (data.get("time_text") or "").strip()
    try:
        steps = load_manual(name)
    except ManualError as e:
        return jsonify({"error": str(e)}), 400
    step = next((s for s in steps if s["key"] == step_key), None)
    if step is None:
        # CSVが書き換わって手順が消えた場合。画面を読み直せば直る
        return jsonify({"error": "この手順はマニュアルにありません。画面を更新してください。"}), 400

    eid = M.add_entry(g.db, rid, time_text=time_text, content=step["record_text"])
    P.mark_done(
        g.db, rid,
        manual_file=name, step_key=step_key, done_time=time_text, entry_id=eid,
    )
    _alog("マニュアル実施", f"記録ID {rid} / 行ID {eid}", f"{name} / {time_text} {step['record_text']}")
    return jsonify({
        "entry": row_to_dict(M.get_entry(g.db, eid)),
        "progress": _progress_dict(rid, name),
    }), 201


@bp.post("/records/<int:rid>/manual_steps/undo")
def undo_manual_step(rid):
    """「元に戻す」：直前に追加した記録行を消し、その手順を未実施に戻す。"""
    if not M.get_record(g.db, rid):
        abort(404)
    _require_not_finalized(rid)
    data = request.get_json(silent=True) or {}
    name = _manual_arg()
    step_key = (data.get("step_key") or "").strip()
    entry_id = data.get("entry_id")

    if entry_id is not None:
        row = M.get_entry(g.db, entry_id)
        # 他の記録の行を消してしまわないよう、この記録の行であることを確かめる
        if row is not None and row["record_id"] == rid:
            M.delete_entry(g.db, entry_id)
    P.clear_step(g.db, rid, manual_file=name, step_key=step_key)
    _alog("マニュアル実施の取消", f"記録ID {rid} / 行ID {entry_id}", f"{name} / {step_key}")
    return jsonify({"progress": _progress_dict(rid, name)})


@bp.post("/records/<int:rid>/manual_progress/reset")
def reset_manual_progress(rid):
    """進捗（色）だけをまとめて消す。追加済みの記録行は残す。"""
    if not M.get_record(g.db, rid):
        abort(404)
    _require_not_finalized(rid)
    name = _manual_arg()
    n = P.clear_manual(g.db, rid, manual_file=name)
    _alog("マニュアル進捗リセット", f"記録ID {rid}", f"{name} / {n}件")
    return jsonify({"progress": {}, "cleared": n})
