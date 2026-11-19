"""他PC・単体アプリのデータを統合アプリへ取り込む。

使い方:
    python tools/import_data.py "<フォルダ または records.db のパス>"

ドロップされた records.db のテーブル構成から、運転記録／点検チェックリストの
どちらのデータかを自動判定し、対応するDB（data/work.db または data/check.db）へ
取り込む。取り込み前に現在のDBは *_before_import_日時.db へ自動退避する（非破壊・取り込むたびに別名で残る）。
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent   # facility-logbook
DATA = BASE / "data"


def _resolve_db(src: Path) -> Path | None:
    """フォルダなら records.db、records.db ファイルが直接渡された場合はそれを返す。"""
    if src.is_dir():
        cand = src / "records.db"
        return cand if cand.exists() else None
    if src.suffix.lower() == ".db" and src.exists():
        return src
    cand = src / "records.db"
    return cand if cand.exists() else None


def _detect_kind(db_path: Path) -> str | None:
    con = sqlite3.connect(str(db_path))
    try:
        tables = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()
    if {"records", "entries"} & tables:
        return "work"
    if {"inspections", "inspection_items"} & tables:
        return "check"
    return None


def _copy_tree_merge(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True)


def run(raw: str) -> int:
    src = Path(raw.strip().strip('"').rstrip("\\").rstrip("/"))
    db = _resolve_db(src)
    if db is None:
        print(f"[エラー] records.db が見つかりません: {src}")
        print("運転記録／点検アプリのフォルダ、または records.db ファイルを指定してください。")
        return 1

    kind = _detect_kind(db)
    if kind is None:
        print("[エラー] この records.db は運転記録／点検のどちらにも該当しません。")
        return 1

    label = "運転記録" if kind == "work" else "点検チェックリスト"
    print(f"判定: 「{label}」のデータとして取り込みます。")

    DATA.mkdir(parents=True, exist_ok=True)
    target = DATA / ("work.db" if kind == "work" else "check.db")

    # 現在のDBを退避（非破壊）
    if target.exists():
        bak = DATA / f"{target.stem}_before_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(target, bak)
        print(f"現在の{label}データを {bak.name} へ退避しました。（元に戻す場合はこのファイルを使用）")

    shutil.copy2(db, target)
    print(f"{label}の記録データ（records.db）を取り込みました。")

    srcdir = db.parent
    if kind == "work":
        up = srcdir / "uploads"
        if up.is_dir():
            dst = BASE / "uploads"
            dst.mkdir(parents=True, exist_ok=True)
            n = 0
            for f in up.iterdir():
                if f.is_file():
                    shutil.copy2(f, dst / f.name)
                    n += 1
            print(f"写真（uploads）を {n} 件取り込みました。")
    else:  # check
        eq = srcdir / "equipments"
        if eq.is_dir():
            _copy_tree_merge(eq, BASE / "check" / "equipments")
            print("点検フォーム設定（equipments：チェック項目・PDF様式・記入位置）を取り込みました。")

    print("")
    print("取り込みが完了しました。「起動.bat」でサーバを起動して内容を確認してください。")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("使い方: import_data.py \"<フォルダ または records.db のパス>\"")
        sys.exit(1)
    sys.exit(run(sys.argv[1]))
