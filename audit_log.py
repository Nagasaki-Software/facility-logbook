"""編集ログ（監査ログ）の記録。

ログイン機能が無いため「誰が」はアクセス元のIPアドレスで記録する。
運転記録・点検の両方から呼ばれ、共有のCSV（data/audit_log.csv）へ追記する。
Excel で開けるよう UTF-8(BOM付き) で作成する。失敗しても本処理は止めない。
"""
import csv
import threading
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
LOG_DIR = BASE / "data"
LOG_FILE = LOG_DIR / "audit_log.csv"
HEADER = ["日時", "IPアドレス", "アプリ", "操作", "対象", "内容"]

_lock = threading.Lock()


def write_log(ip, app_name, action, target="", detail=""):
    """1件の編集ログを追記する。ip はアクセス元IP（不明時は '?'）。"""
    try:
        now = datetime.now().isoformat(sep=" ", timespec="seconds")
        row = [now, ip or "?", app_name, action, str(target), str(detail)]
        with _lock:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            new_file = not LOG_FILE.exists()
            if new_file:
                # 新規作成時のみ BOM 付きでヘッダを書く（追記時のBOM混入を防ぐ）
                with open(LOG_FILE, "w", encoding="utf-8-sig", newline="") as f:
                    csv.writer(f).writerow(HEADER)
            with open(LOG_FILE, "a", encoding="utf-8", newline="") as f:
                csv.writer(f).writerow(row)
    except Exception:
        # ログ記録の失敗で、本来の保存・更新処理を止めない
        pass
