"""統合アプリ エントリポイント。

運転記録アプリ（/work）と点検チェックリストアプリ（/check）を、
1つのサーバー（ポート6060）の中でURL接頭辞ごとにマウントして提供する。
ルート(/) は運転記録(/work/)へリダイレクトする。
"""
import json
import os
import socket
import sys
from pathlib import Path

APP_VERSION = "0.1.0"  # 版数の出どころはここだけ（Releases の版と合わせる）

BASE = Path(__file__).resolve().parent
# 自分のフォルダを import パスへ（work / check パッケージを解決するため）
sys.path.insert(0, str(BASE))

from flask import Flask, redirect
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple

from work.app import create_app as create_work_app
from work.database import init_db as work_init_db
from work.backup import start_backup_thread
from check.app import create_app as create_check_app
from check.database import init_db as check_init_db

# ── パス定義 ──────────────────────────────────────────────
DATA_DIR    = BASE / "data"
UPLOAD_DIR  = BASE / "uploads"
BACKUP_DIR  = BASE / "backup"
OUTPUT_DIR  = BASE / "output"
WORK_DB     = DATA_DIR / "work.db"
CHECK_DB    = DATA_DIR / "check.db"

for d in (DATA_DIR, UPLOAD_DIR, BACKUP_DIR, OUTPUT_DIR):
    d.mkdir(parents=True, exist_ok=True)


def _load_port(default=6060):
    p = BASE / "config.json"
    if p.exists():
        try:
            return int(json.loads(p.read_text(encoding="utf-8")).get("port", default))
        except Exception:
            return default
    return default


def _port_in_use(port: int) -> bool:
    """指定ポートで既にサーバが応答するかを確認する（2重起動の検出）。
    接続できれば「既に起動中」と判断する。Windows の SO_REUSEADDR で
    bind が成功してしまう問題を避けるため、bind ではなく connect で確認する。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


def build_application():
    # DBを初期化（存在すればそのまま使う＝既存データを保持）
    work_init_db(str(WORK_DB))
    check_init_db(db_path=str(CHECK_DB), schema_path=str(BASE / "check" / "schema.sql"))

    # 運転記録アプリ
    work_app = create_work_app({
        "DATABASE":   str(WORK_DB),
        "UPLOAD_DIR": str(UPLOAD_DIR),
        "BACKUP_DIR": str(BACKUP_DIR),
    })

    # 点検チェックリストアプリ
    check_app = create_check_app({
        "db_path":        str(CHECK_DB),
        "equipments_dir": str(BASE / "check" / "equipments"),
        "output_dir":     str(OUTPUT_DIR),
        "title_file":     str(BASE / "check" / "title.txt"),
        "inspectors_csv": str(BASE / "check" / "inspectors.csv"),
        "config_json":    str(BASE / "config.json"),
    })

    # ルート: / は運転記録へ
    root = Flask(__name__)

    @root.route("/")
    def home():
        return redirect("/work/")

    application = DispatcherMiddleware(root, {
        "/work":  work_app,
        "/check": check_app,
    })
    return application


def main():
    port = _load_port()
    # 2重起動の防止：すでに同じポートで起動中なら、はっきり知らせて中止する
    if _port_in_use(port):
        print("=" * 56)
        print(f"[起動中止] ポート {port} は既に使用中です。")
        print("統合アプリが既に起動している可能性があります（2重起動の防止）。")
        print("開いている黒い画面（サーバー）をすべて閉じてから、")
        print("もう一度この『起動.bat』を実行してください。")
        print("=" * 56)
        return
    app = build_application()
    # 運転記録DB・点検DBの日次バックアップを開始（backup フォルダへ records_*.db / check_*.db）
    start_backup_thread(WORK_DB, BACKUP_DIR, keep_days=90, extra=((CHECK_DB, "check"),))
    print(f"統合アプリを起動します（バージョン {APP_VERSION}）  ->  http://127.0.0.1:{port}/")
    print("停止するにはこの画面を閉じるか Ctrl+C を押してください。")
    run_simple("0.0.0.0", port, app, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
