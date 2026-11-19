"""古い版のフォルダから、記録・設定・設備などを、新しい版のフォルダへ写す（データ引き継ぎ.bat から呼ぶ）。

古いフォルダの中身は変えない（読むだけ）。新しいフォルダの見本の設備・手順表は「見本データ」フォルダへ移してから写す。
標準ライブラリだけで動く（初回セットアップの前でも使えるように）。
"""
import json
import shutil
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

DEFAULT_PORT = 6060
SAMPLE_DIR = "見本データ"
DB_FILES = ("work.db", "check.db")
# いつも写すもの（無ければ飛ばす）
FIXED = ["config.json", "data", "uploads", "backup", "output",
         "check/equipments", "check/inspectors.csv", "check/title.txt",
         "work/manuals", "work/app_title.txt",
         "確定解除リスト.txt", "点検修正リスト.txt"]
# 新しい版に見本が入っているフォルダ（古いほうに無い見本は「見本データ」へ移す）
SAMPLE_FOLDERS = ["check/equipments", "work/manuals"]


class MigrateError(Exception):
    pass


def app_is_running(folder):
    """そのフォルダの config.json のポート（無ければ 6060）で、このアプリが返事をするか。"""
    port = DEFAULT_PORT
    try:
        cfg = json.loads((Path(folder) / "config.json").read_text(encoding="utf-8-sig"))
        if isinstance(cfg, dict) and str(cfg.get("port", "")).isdigit():
            port = int(cfg["port"])
    except (OSError, ValueError):
        pass
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/work/api/button_groups", timeout=2) as r:
            json.loads(r.read().decode("utf-8"))
            return True
    except (OSError, ValueError):
        return False


def _copy(src, dst):
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _count(path):
    return sum(1 for p in path.rglob("*") if p.is_file()) if path.is_dir() else 1


def migrate(old, new, overwrite_db=False, is_running=app_is_running):
    """写した内容を、画面に出す行のリストで返す。写せないときは MigrateError（何も写さない）。"""
    old, new = Path(old), Path(new)
    if not old.is_dir():
        raise MigrateError(f"古いフォルダが見つかりません: {old}")
    if old.resolve() == new.resolve():
        raise MigrateError("古いフォルダに、この新しいフォルダが指定されています。古い版のフォルダを指定してください")
    if not (old / "run.py").is_file() or not (old / "work").is_dir() or not (old / "check").is_dir():
        raise MigrateError(f"このアプリのフォルダではないようです（run.py と work・check がありません）: {old}")
    if is_running(old):
        raise MigrateError("アプリが動いています。黒い窓を閉じるか Ctrl + C を押して止めてから、もう一度実行してください")
    if any((new / "data" / n).exists() for n in DB_FILES) and not overwrite_db:
        raise MigrateError("新しいフォルダには、すでに記録（data\\work.db・check.db）があります。新しいフォルダで一度起動したためです")

    report = []
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 新しいフォルダの記録を上書きするときは、消さずに見本データへ移しておく
    if (new / "data").is_dir() and any((new / "data" / n).exists() for n in DB_FILES):
        keep = new / SAMPLE_DIR / f"上書き前のdata_{stamp}"
        keep.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(new / "data"), str(keep))
        report.append(f"新しいフォルダの記録は {keep.relative_to(new)} へ移しました")

    # 見本の設備・手順表（古いほうに無いもの）を見本データへ移す。混ざらないように
    for rel in SAMPLE_FOLDERS:
        src_old, src_new = old / rel, new / rel
        if not src_old.is_dir() or not src_new.is_dir():
            continue
        moved = 0
        for f in src_new.iterdir():
            if not (src_old / f.name).exists():
                dst = new / SAMPLE_DIR / rel / f.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(f), str(dst))
                moved += 1
        if moved:
            report.append(f"見本の {rel} の {moved} 個を {SAMPLE_DIR}\\{Path(rel)} へ移しました")

    for rel in FIXED:
        src = old / rel
        if not src.exists():
            continue
        _copy(src, new / rel)
        n = _count(src)
        report.append(f"写しました: {Path(rel)}" + (f"（ファイル {n} 個）" if src.is_dir() else ""))
    return report


def main(argv):
    new = Path(__file__).resolve().parent
    print("============================================")
    print(" facility-logbook データ引き継ぎ")
    print("============================================")
    print(f"新しい版のフォルダ: {new}")
    print()
    raw = argv[1] if len(argv) > 1 else input("古い版のフォルダの場所を入れて Enter を押してください（フォルダをこの窓へドラッグしても入ります）\n> ")
    old = Path(raw.strip().strip('"'))
    overwrite = False
    while True:
        try:
            report = migrate(old, new, overwrite_db=overwrite)
            break
        except MigrateError as e:
            print()
            print("[止めました] " + str(e))
            if "すでに記録" in str(e) and not overwrite:
                ans = input("古いフォルダの内容で上書きしますか？（新しいフォルダの記録は「見本データ」に残します） y / n > ")
                if ans.strip().lower() == "y":
                    overwrite = True
                    continue
            print("何も写していません。")
            return 1
    print()
    for line in report:
        print("  " + line)
    print()
    print("引き継ぎが終わりました。古いフォルダはそのまま残っています。")
    print("次に「初回セットアップ.bat」、そのあと「起動.bat」を実行してください。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
