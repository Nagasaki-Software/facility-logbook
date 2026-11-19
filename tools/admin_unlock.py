"""管理者用：確定済みの運転記録を「確定解除」して、再びアプリで修正できるようにする。

使い方:
    python tools/admin_unlock.py 12 15      # 記録ID 12 と 15 を解除
    python tools/admin_unlock.py            # 引数なしの場合は確定解除リスト.txt を読む

確定解除すると finalized=0 になり、アプリでその記録を開けば編集できる。
修正後はアプリで再度「終了」を押して確定し直すこと。
※ 安全のため、できればサーバ（起動.bat）を停止してから実行する。
"""
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent  # facility-logbook
sys.path.insert(0, str(BASE))                  # work パッケージを import するため
WORK_DB = BASE / "data" / "work.db"
LIST_FILE = BASE / "確定解除リスト.txt"

try:
    import audit_log
except Exception:
    audit_log = None


def _ensure_schema():
    """finalized 列など最新スキーマを保証する（サーバ未起動でも安全に実行できるように）。"""
    try:
        from work.database import init_db
        init_db(WORK_DB)
    except Exception as e:
        print(f"[警告] スキーマ更新をスキップしました: {e}")


def _ids_from_list_file():
    """確定解除リスト.txt（VSCode等で編集可）から記録IDを読む。# 始まりはコメント。"""
    if not LIST_FILE.exists():
        return []
    ids = []
    for line in LIST_FILE.read_text(encoding="utf-8-sig").splitlines():
        s = line.split("#", 1)[0].strip()
        if s.isdigit():
            ids.append(int(s))
    return ids


def main(argv):
    raw = [a for a in argv if a.strip()]
    ids = [int(a) for a in raw if a.lstrip("-").isdigit()] if raw else _ids_from_list_file()
    if not ids:
        print("解除する記録IDが指定されていません。")
        print("例) python tools/admin_unlock.py 12   または 確定解除リスト.txt にIDを記入")
        return 1
    if not WORK_DB.exists():
        print(f"[エラー] データベースが見つかりません: {WORK_DB}")
        return 1

    _ensure_schema()  # finalized 列を保証

    con = sqlite3.connect(str(WORK_DB))
    con.row_factory = sqlite3.Row
    try:
        for rid in ids:
            row = con.execute(
                "SELECT id, record_date, title, finalized FROM records WHERE id = ?", (rid,)
            ).fetchone()
            if row is None:
                print(f"  ID {rid}: 該当する記録がありません（スキップ）")
                continue
            if not row["finalized"]:
                print(f"  ID {rid}: もともと確定されていません（{row['record_date']} {row['title']}）")
                continue
            con.execute("UPDATE records SET finalized = 0 WHERE id = ?", (rid,))
            print(f"  ID {rid}: 確定解除しました（{row['record_date']} {row['title']}）")
            if audit_log:
                audit_log.write_log("管理者PC(ローカル)", "運転記録", "確定解除(管理者)",
                                    f"記録ID {rid}", f"{row['record_date']} {row['title']}")
        con.commit()
    finally:
        con.close()

    print("")
    print("完了。アプリでこの記録を開けば修正できます。修正後は再度「終了」で確定してください。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
