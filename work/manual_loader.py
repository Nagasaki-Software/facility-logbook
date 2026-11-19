"""運転マニュアル（手順表）CSVの読み込みと検証。

CSVは work/manuals/ に置く。列は 区分,手順,作業内容,備考,記録内容。
「作業内容」だけが必須で、進捗の保存キーにも使うため各行で一意にする。
"""
import csv
import io
from pathlib import Path

REQUIRED = ["作業内容"]
COLUMNS = ["区分", "手順", "作業内容", "備考", "記録内容"]


class ManualError(Exception):
    pass


def manuals_dir() -> Path:
    return Path(__file__).parent / "manuals"


def list_manuals() -> list[str]:
    d = manuals_dir()
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.glob("*.csv") if p.is_file())


def _resolve(name: str) -> Path:
    # ファイル名だけを受け取る（区切り文字を含むものは拒否＝上位フォルダへの遡上を防ぐ）
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise ManualError("マニュアル名が不正です")
    p = manuals_dir() / name
    if p.suffix.lower() != ".csv" or not p.is_file():
        raise ManualError(f"マニュアルが見つかりません: {name}")
    return p


def _read_text(path: Path) -> str:
    # Excel から「CSV UTF-8」で保存すると utf-8-sig、ふつうの「CSV」だと cp932 になる
    data = path.read_bytes()
    for enc in ("utf-8-sig", "cp932"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ManualError(
        "文字コードを判別できません。CSVを UTF-8 または Shift-JIS で保存し直してください。"
    )


def load_manual(name: str) -> list[dict]:
    path = _resolve(name)
    reader = csv.DictReader(io.StringIO(_read_text(path), newline=""))
    if reader.fieldnames is None:
        raise ManualError("CSVが空です")
    headers = [(h or "").strip() for h in reader.fieldnames]
    for col in REQUIRED:
        if col not in headers:
            raise ManualError(
                f"必須列がありません: {col}"
                f"（1行目に {','.join(COLUMNS)} と書いてください）"
            )

    steps = []
    seen = {}   # 作業内容 -> 何行目で出たか（重複検出用）
    for i, raw in enumerate(reader):
        line = i + 2   # ヘッダ=1行目
        row = {(k.strip() if k else k): (v or "").strip() for k, v in raw.items()}
        content = row.get("作業内容", "")
        if content == "" and not any(row.get(c) for c in COLUMNS):
            continue   # 完全な空行はスキップ
        if content == "":
            raise ManualError(f"{line}行目: 「作業内容」が空です。手順の文章を入れてください。")
        if content in seen:
            raise ManualError(
                f"{line}行目: 作業内容『{content}』が重複しています"
                f"（{seen[content]}行目と同じ）。各行で異なる文章にしてください。"
            )
        seen[content] = line
        steps.append({
            "key": content,                                  # 進捗の保存キー
            "section": row.get("区分", ""),
            "step_no": row.get("手順", ""),
            "content": content,
            "note": row.get("備考", ""),
            "record_text": row.get("記録内容", "") or content,  # 空なら作業内容をそのまま記録
        })

    if not steps:
        raise ManualError("手順が1件もありません。2行目以降に作業内容を入れてください。")
    return steps
