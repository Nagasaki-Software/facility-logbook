"""アプリ更新：このフォルダ(最新版)のプログラムファイルだけを、指定した既存アプリへ上書きする。

data / uploads / backup / output / equipments / manuals / inspectors.csv / title.txt /
config.json / .venv などのデータ・設定は一切コピーしないため、更新先PCの記録・設定は
そのまま保持される。
work/app_title.txt（運転記録のタイトル）と、管理者が書き込む 確定解除リスト.txt /
点検修正リスト.txt は、更新先に既にあれば上書きしない（無いときだけ最新版のひな形を入れる）。

使い方:
    python tools/update_app.py "<更新したい既存アプリのフォルダ>"
※ 安全のため、更新先アプリのサーバ（起動.bat の黒い画面）は停止してから実行する。
"""
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent   # このパッケージ(最新版)のルート

# コピーしない＝更新先のデータ・設定（絶対に触らない）
EXCLUDE_DIRS = {"data", "uploads", "backup", "output", ".venv", ".git", ".github",
                ".claude", "__pycache__", ".pytest_cache", "equipments", "manuals",
                "docs", "tests"}
EXCLUDE_FILES = {"config.json", "inspectors.csv", "title.txt"}
EXCLUDE_EXTS = {".db", ".pyc", ".log", ".sqlite", ".sqlite3"}
# 更新先に既にあれば上書きしない（無いときだけコピー）＝現場で書き換える設定・リスト
KEEP_IF_EXISTS = {"work/app_title.txt", "確定解除リスト.txt", "点検修正リスト.txt"}


def _is_app_folder(p):
    return (p / "run.py").exists() or (p / "check").is_dir()


def _skip_file(name):
    return name in EXCLUDE_FILES or Path(name).suffix.lower() in EXCLUDE_EXTS


def _seed_manuals(dst):
    """運転マニュアルは現場で編集するCSVなので上書きしないが、
    更新先にまだフォルダが無いとき（機能追加前のアプリ）だけサンプルを入れる。
    これが無いと新機能を入れてもマニュアルのタブが出ない。"""
    src = SRC / "work" / "manuals"
    target = dst / "work" / "manuals"
    if not src.is_dir() or target.exists():
        return None
    shutil.copytree(src, target)
    return target


def _backup_data(dst):
    data = dst / "data"
    if not data.is_dir():
        return None
    bak = dst / f"data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copytree(data, bak)
    return bak


def main(argv):
    if not argv or not argv[0].strip():
        print("更新したい既存アプリのフォルダを指定してください。")
        return 1
    dst = Path(argv[0].strip().strip('"')).resolve()

    if not dst.is_dir():
        print(f"[エラー] フォルダが見つかりません: {dst}")
        return 1
    if dst == SRC:
        print("[エラー] コピー元とコピー先が同じです。更新したい『既存アプリ』のフォルダを指定してください。")
        return 1
    if not _is_app_folder(dst):
        print(f"[エラー] アプリのフォルダではないようです（run.py が見つかりません）: {dst}")
        return 1

    print(f"最新版: {SRC}")
    print(f"更新先: {dst}")
    print("プログラムファイルだけを上書きします（データ・設定は保持）。")

    bak = _backup_data(dst)
    if bak:
        print(f"念のため data を退避しました: {bak.name}")

    copied = 0
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]   # 除外フォルダには降りない
        rel_dir = Path(root).relative_to(SRC)
        for fn in files:
            if _skip_file(fn):
                continue
            target = dst / rel_dir / fn
            if (rel_dir / fn).as_posix() in KEEP_IF_EXISTS and target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(root) / fn, target)
            copied += 1

    seeded = _seed_manuals(dst)
    if seeded:
        print("運転マニュアルのサンプルCSVを work\\manuals へ入れました（既にある場合は触りません）。")

    print("")
    print(f"完了：{copied} 個のプログラムファイルを更新しました。")
    print("更新先アプリを「起動.bat」で起動し、ブラウザは Ctrl+F5 で再読み込みしてください。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
