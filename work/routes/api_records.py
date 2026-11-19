import os
import uuid
from pathlib import Path

from flask import Blueprint, g, jsonify, request, abort, current_app, send_file
from ..models import records as M
from ._helpers import row_to_dict
from ..backup import perform_backup
import audit_log


def _alog(action, target="", detail=""):
    audit_log.write_log(request.remote_addr, "運転記録", action, target, detail)

bp = Blueprint("api_records", __name__, url_prefix="/api")

MAX_RECORD_PHOTOS = 3
ALLOWED_PHOTO_EXT = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "heic"}


def _upload_dir() -> str:
    d = current_app.config["UPLOAD_DIR"]
    os.makedirs(d, exist_ok=True)
    return d


def _remove_photo_file(filename: str) -> None:
    try:
        os.remove(os.path.join(current_app.config["UPLOAD_DIR"], filename))
    except OSError:
        pass


def _photo_dict(row) -> dict:
    return {
        "id": row["id"],
        "url": f"/uploads/{row['filename']}",                 # 拡大表示（ブラウザで開く）
        "download_url": f"/api/photos/{row['id']}/download",   # ダウンロード
        "original_name": row["original_name"],
        "memo": row["memo"],
    }


def _require_not_finalized(record_id) -> None:
    """確定済みの記録は編集禁止（管理者が確定解除しない限り変更不可）。"""
    if record_id is not None and M.is_finalized(g.db, record_id):
        abort(403, "確定済みの記録のため編集できません。修正は管理者へ依頼してください。")


@bp.post("/records")
def create_record():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "")
    record_date = data.get("record_date")
    if not record_date:
        abort(400, "record_date required")
    rid = M.create_record(g.db, title=title, record_date=record_date)
    _alog("記録作成", f"記録ID {rid}", f"{record_date} / {title}")
    return jsonify(row_to_dict(M.get_record(g.db, rid))), 201


@bp.get("/records/current")
def get_current():
    row = M.get_current_record(g.db)
    if not row:
        abort(404)
    return jsonify(row_to_dict(row))


@bp.get("/records/<int:rid>")
def get_record(rid):
    row = M.get_record(g.db, rid)
    if not row:
        abort(404)
    return jsonify(row_to_dict(row))


@bp.post("/records/<int:rid>/finish")
def finish_record(rid):
    # 「終了」＝確定。サーバに保存し、全ユーザーへ共有される（以降は編集不可）。
    if not M.get_record(g.db, rid):
        abort(404)
    M.set_finalized(g.db, rid, 1)
    _alog("確定(終了)", f"記録ID {rid}")
    return jsonify(row_to_dict(M.get_record(g.db, rid)))


@bp.patch("/records/<int:rid>")
def patch_record(rid):
    _require_not_finalized(rid)
    data = request.get_json(silent=True) or {}
    record_date = data.get("record_date")
    if not record_date:
        abort(400, "record_date required")
    ok = M.update_record_header(
        g.db, rid,
        title=data.get("title", ""),
        record_date=record_date,
    )
    if not ok:
        abort(404)
    _alog("見出し変更", f"記録ID {rid}", f"{data.get('title','')} / {record_date}")
    return jsonify(row_to_dict(M.get_record(g.db, rid)))


@bp.delete("/records/<int:rid>")
def delete_record(rid):
    _require_not_finalized(rid)
    # 添付写真ファイルも消す（DB行は CASCADE で消える）
    for p in M.list_record_photos(g.db, rid):
        _remove_photo_file(p["filename"])
    M.delete_record(g.db, rid)  # silent ignore if missing
    _alog("記録削除", f"記録ID {rid}")
    return "", 204


@bp.get("/records/<int:rid>/photos")
def list_record_photos(rid):
    photos = [_photo_dict(p) for p in M.list_record_photos(g.db, rid)]
    return jsonify({"photos": photos, "max": MAX_RECORD_PHOTOS})


@bp.post("/records/<int:rid>/photos")
def add_record_photo(rid):
    if not M.get_record(g.db, rid):
        abort(404)
    _require_not_finalized(rid)
    if M.count_record_photos(g.db, rid) >= MAX_RECORD_PHOTOS:
        abort(400, f"添付は最大{MAX_RECORD_PHOTOS}枚までです")
    file = request.files.get("photo")
    if file is None or not file.filename:
        abort(400, "photo file required")
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    if ext not in ALLOWED_PHOTO_EXT:
        abort(400, "画像ファイルを選んでください")
    fname = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(_upload_dir(), fname))
    pid = M.add_record_photo(
        g.db, rid,
        filename=fname,
        original_name=file.filename,
        memo=(request.form.get("memo") or "").strip(),
    )
    _alog("写真追加", f"記録ID {rid}", file.filename)
    return jsonify(_photo_dict(M.get_record_photo(g.db, pid))), 201


@bp.patch("/photos/<int:pid>")
def patch_record_photo(pid):
    row = M.get_record_photo(g.db, pid)
    if not row:
        abort(404)
    _require_not_finalized(row["record_id"])
    memo = ((request.get_json(silent=True) or {}).get("memo") or "").strip()
    if not M.update_record_photo_memo(g.db, pid, memo=memo):
        abort(404)
    return jsonify({"ok": True})


@bp.delete("/photos/<int:pid>")
def delete_record_photo(pid):
    row = M.get_record_photo(g.db, pid)
    if row:
        _require_not_finalized(row["record_id"])
        M.delete_record_photo(g.db, pid)
        _remove_photo_file(row["filename"])
        _alog("写真削除", f"写真ID {pid}")
    return "", 204


@bp.get("/photos/<int:pid>/download")
def download_record_photo(pid):
    row = M.get_record_photo(g.db, pid)
    if not row:
        abort(404)
    path = os.path.join(os.path.abspath(current_app.config["UPLOAD_DIR"]), row["filename"])
    if not os.path.exists(path):
        abort(404)
    name = row["original_name"] or row["filename"]
    return send_file(path, as_attachment=True, download_name=name)


@bp.get("/search")
def search_records():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"records": []})
    return jsonify({"records": [row_to_dict(r) for r in M.search_records(g.db, q)]})


@bp.get("/content_suggestions")
def content_suggestions():
    # 日付の区切り行（―― … ――）は候補から除く
    items = [c for c in M.recent_contents(g.db, 40) if not c.startswith("――")]
    return jsonify({"suggestions": items[:30]})


@bp.get("/records")
def list_records():
    date = request.args.get("date")
    if date:
        rows = M.list_records_on_date(g.db, date)
    else:
        year = request.args.get("year", type=int)
        month = request.args.get("month", type=int)
        if not (year and month):
            abort(400, "year and month or date required")
        rows = M.list_records_in_month(g.db, year=year, month=month)
    return jsonify({"records": [row_to_dict(r) for r in rows]})


@bp.post("/records/<int:rid>/entries")
def add_entry(rid):
    if not M.get_record(g.db, rid):
        abort(404)
    _require_not_finalized(rid)
    data = request.get_json(silent=True) or {}
    # after_id: 省略時は末尾に追加。0 で先頭に挿入。N で entry N の直後に挿入。
    after_id = data.get("after_id")
    eid = M.add_entry(
        g.db, rid,
        time_text=data.get("time_text", ""),
        content=data.get("content", ""),
        after_id=after_id,
    )
    rows = M.list_entries(g.db, rid)
    new_row = next(r for r in rows if r["id"] == eid)
    _alog("行追加", f"記録ID {rid} / 行ID {eid}", f"{data.get('time_text','')} {data.get('content','')}".strip())
    return jsonify(row_to_dict(new_row)), 201


@bp.get("/records/<int:rid>/entries")
def list_entries(rid):
    return jsonify({
        "entries": [row_to_dict(r) for r in M.list_entries(g.db, rid)]
    })


@bp.post("/records/<int:rid>/entries/reorder")
def reorder_entries(rid):
    _require_not_finalized(rid)
    ids = (request.get_json(silent=True) or {}).get("ordered_ids", [])
    M.set_entries_order(g.db, rid, ids)
    return jsonify({"ok": True})


@bp.post("/backup")
def manual_backup():
    # 今のデータベースを backup フォルダへ即時バックアップする
    src = Path(current_app.config["DATABASE"])
    dest = Path(current_app.config["BACKUP_DIR"])
    target = perform_backup(src, dest)
    return jsonify({"ok": True, "filename": target.name})


@bp.patch("/entries/<int:eid>")
def patch_entry(eid):
    ent = M.get_entry(g.db, eid)
    if not ent:
        abort(404)
    _require_not_finalized(ent["record_id"])
    data = request.get_json(silent=True) or {}
    ok = M.update_entry(
        g.db, eid,
        time_text=data.get("time_text", ""),
        content=data.get("content", ""),
    )
    if not ok:
        abort(404)
    _alog("行編集", f"行ID {eid}", f"{data.get('time_text','')} {data.get('content','')}".strip())
    return jsonify({"ok": True})


@bp.patch("/entries/<int:eid>/important")
def patch_entry_important(eid):
    ent = M.get_entry(g.db, eid)
    if not ent:
        abort(404)
    _require_not_finalized(ent["record_id"])
    data = request.get_json(silent=True) or {}
    # level: 0=なし / 1=黄 / 2=ピンク（後方互換: important=true は 1 として扱う）
    if "level" in data:
        try:
            level = int(data.get("level") or 0)
        except (TypeError, ValueError):
            level = 0
    else:
        level = 1 if data.get("important") else 0
    if level not in (0, 1, 2):
        level = 0
    ok = M.set_entry_important(g.db, eid, level=level)
    if not ok:
        abort(404)
    _alog("色変更", f"行ID {eid}", f"レベル {level}")
    return jsonify({"ok": True})


@bp.delete("/entries/<int:eid>")
def delete_entry(eid):
    ent = M.get_entry(g.db, eid)
    if ent:
        _require_not_finalized(ent["record_id"])
        M.delete_entry(g.db, eid)
        _alog("行削除", f"行ID {eid}")
    return "", 204
