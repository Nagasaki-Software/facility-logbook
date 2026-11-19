import io
from datetime import date as _date
from flask import Blueprint, g, request, send_file, abort
from ..models import records as M
from ._helpers import row_to_dict
from ..excel_export import (
    build_single_workbook, build_multi_workbook,
    filename_for_single, filename_for_range,
)
from ..pdf_export import build_single_pdf, filename_for_single_pdf

bp = Blueprint("api_export", __name__, url_prefix="/api")
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@bp.get("/records/<int:rid>/export")
def export_single(rid):
    rec = M.get_record(g.db, rid)
    if not rec:
        abort(404)
    rec_d = row_to_dict(rec)
    entries = [row_to_dict(e) for e in M.list_entries(g.db, rid)]
    wb = build_single_workbook(rec_d, entries)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        mimetype=XLSX_MIME,
        as_attachment=True,
        download_name=filename_for_single(rec_d),
    )


@bp.get("/records/<int:rid>/pdf")
def export_single_pdf(rid):
    rec = M.get_record(g.db, rid)
    if not rec:
        abort(404)
    rec_d = row_to_dict(rec)
    entries = [row_to_dict(e) for e in M.list_entries(g.db, rid)]
    pdf = build_single_pdf(rec_d, entries)
    return send_file(
        io.BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename_for_single_pdf(rec_d),
    )


@bp.get("/export")
def export_range():
    start = request.args.get("from")
    end = request.args.get("to")
    if not (start and end):
        abort(400, "from and to required")
    try:
        _date.fromisoformat(start)
        _date.fromisoformat(end)
    except ValueError:
        abort(400, "from/to must be YYYY-MM-DD")

    rows = M.list_records_between(g.db, start=start, end=end)
    pairs = []
    for r in rows:
        rec_d = row_to_dict(r)
        entries = [row_to_dict(e) for e in M.list_entries(g.db, r["id"])]
        pairs.append((rec_d, entries))

    wb = build_multi_workbook(pairs)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        mimetype=XLSX_MIME,
        as_attachment=True,
        download_name=filename_for_range(start, end),
    )
