"""管理者用：過去の点検結果を「編集可にする（修正解除）」または「削除する」。

使い方:
    python tools/check_unlock.py 12 15            # 点検ID 12,15 を編集可にする
    python tools/check_unlock.py                  # 引数なしは 点検修正リスト.txt を読む（編集可）
    python tools/check_unlock.py --delete 12 15   # 点検ID 12,15 を削除する（確認あり・元に戻せない）

編集可にすると、アプリの「過去の点検結果」一覧に「修正」リンクが出る。
そこから記録画面に呼び出して修正し、保存すると上書きされ、自動で編集不可に戻る。
削除は確認（yes 入力）の後に、その点検と明細を完全に削除する。
※ 安全のため、できればサーバ（起動.bat）を停止してから実行する。
"""
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent  # facility-logbook
sys.path.insert(0, str(BASE))                  # check パッケージを import するため
CHECK_DB = BASE / "data" / "check.db"
LIST_FILE = BASE / "点検修正リスト.txt"

try:
    import audit_log
except Exception:
    audit_log = None


def _ensure_schema():
    """editable 列など最新スキーマを保証する（サーバ未起動でも安全に実行できるように）。"""
    try:
        from check.database import init_db
        init_db(db_path=str(CHECK_DB), schema_path=str(BASE / "check" / "schema.sql"))
    except Exception as e:
        print(f"[警告] スキーマ更新をスキップしました: {e}")


def _ids_from_list_file():
    if not LIST_FILE.exists():
        return []
    ids = []
    for line in LIST_FILE.read_text(encoding="utf-8-sig").splitlines():
        s = line.split("#", 1)[0].strip()
        if s.isdigit():
            ids.append(int(s))
    return ids


def _unlock(ids):
    con = sqlite3.connect(str(CHECK_DB))
    con.row_factory = sqlite3.Row
    try:
        for iid in ids:
            row = con.execute(
                "SELECT id, equipment_key, inspection_date, inspector FROM inspections WHERE id = ?",
                (iid,),
            ).fetchone()
            if row is None:
                print(f"  点検ID {iid}: 該当する点検がありません（スキップ）")
                continue
            con.execute("UPDATE inspections SET editable = 1 WHERE id = ?", (iid,))
            print(f"  点検ID {iid}: 編集可にしました（{row['inspection_date']} / {row['inspector']} / {row['equipment_key']}）")
            if audit_log:
                audit_log.write_log("管理者PC(ローカル)", "点検", "編集可(管理者解除)",
                                    f"点検ID {iid}", f"{row['inspection_date']} / {row['inspector']}")
        con.commit()
    finally:
        con.close()
    print("")
    print("完了。アプリの「過去の点検結果」一覧に出る「修正」リンクから直してください。")
    print("保存すると上書きされ、自動で編集不可に戻ります。")
    return 0


def _delete(ids):
    con = sqlite3.connect(str(CHECK_DB))
    con.row_factory = sqlite3.Row
    try:
        targets = []
        for iid in ids:
            row = con.execute(
                "SELECT id, equipment_key, inspection_date, inspector FROM inspections WHERE id = ?",
                (iid,),
            ).fetchone()
            if row is None:
                print(f"  点検ID {iid}: 該当する点検がありません（スキップ）")
                continue
            targets.append(row)
        if not targets:
            print("削除対象がありません。")
            return 1

        print("以下の点検を削除します（元に戻せません）:")
        for r in targets:
            print(f"  ID {r['id']} : {r['inspection_date']} / {r['inspector']} / {r['equipment_key']}")
        ans = input("本当に削除しますか？ 削除する場合は半角で yes と入力してください: ").strip().lower()
        if ans != "yes":
            print("中止しました。削除していません。")
            return 0

        for r in targets:
            # 明細を先に削除（FK未設定でも確実に消えるように）してから本体を削除
            con.execute("DELETE FROM inspection_items WHERE inspection_id = ?", (r["id"],))
            con.execute("DELETE FROM inspections WHERE id = ?", (r["id"],))
            print(f"  ID {r['id']}: 削除しました")
            if audit_log:
                audit_log.write_log("管理者PC(ローカル)", "点検", "点検削除(管理者)",
                                    f"点検ID {r['id']}", f"{r['inspection_date']} / {r['inspector']} / {r['equipment_key']}")
        con.commit()
    finally:
        con.close()
    print("")
    print("削除が完了しました。")
    return 0


def main(argv):
    delete_mode = ("--delete" in argv) or ("-d" in argv)
    ids = [int(a) for a in argv if a.lstrip("-").isdigit()]
    if not ids and not delete_mode:
        ids = _ids_from_list_file()   # 編集可モードのみ リストファイルを使う（削除は明示ID必須）

    if not ids:
        if delete_mode:
            print("削除する点検IDが指定されていません。例) python tools/check_unlock.py --delete 12")
        else:
            print("編集可にする点検IDが指定されていません。")
            print("例) python tools/check_unlock.py 12   または 点検修正リスト.txt にIDを記入")
        return 1
    if not CHECK_DB.exists():
        print(f"[エラー] データベースが見つかりません: {CHECK_DB}")
        return 1

    _ensure_schema()
    return _delete(ids) if delete_mode else _unlock(ids)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
