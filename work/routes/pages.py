import os
from flask import Blueprint, render_template, current_app, send_from_directory

bp = Blueprint("pages", __name__)


@bp.route("/uploads/<path:filename>")
def uploaded_file(filename):
    # 添付写真を表示する（クリックで拡大）。send_from_directory がパス遡上を防ぐ
    return send_from_directory(os.path.abspath(current_app.config["UPLOAD_DIR"]), filename)


@bp.route("/")
def record_page():
    return render_template(
        "record.html",
        polling_interval=current_app.config["POLLING_INTERVAL"],
    )


@bp.route("/history")
def history_page():
    return render_template("history.html")


@bp.route("/buttons")
def buttons_page():
    return render_template("buttons.html")
