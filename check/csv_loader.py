import csv
import io

REQUIRED = ["点検内容", "種別"]
# meter        = 累計メータ（1行に使用前/使用後をまとめる方式）
# meter_before = 使用前の行 / meter_after = 使用後の行（行を分ける方式。「メータ組」で対応付け）
# time         = 時刻入力（HH:MM。装置起動時刻・薬品供給開始時刻など）
# calc         = 計算項目（「計算式」列で他項目を {項目名} 参照して合計・割合などを自動計算）
VALID_TYPES = {"check", "number", "meter", "meter_before", "meter_after", "time", "calc"}

class ChecklistError(Exception):
    pass

def _to_float(s):
    s = (s or "").strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        raise ChecklistError(f"数値に変換できません: '{s}'")

def _read_text(path):
    # Excel の「CSV UTF-8」は utf-8-sig、ふつうの「CSV」は cp932
    with open(path, "rb") as f:
        data = f.read()
    for enc in ("utf-8-sig", "cp932"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ChecklistError("文字コードを読み取れません。CSVを UTF-8 または Shift-JIS で保存し直してください")

def load_checklist(path):
    text = _read_text(path)
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames is None:
        raise ChecklistError("CSVが空です")
    headers = [h.strip() for h in reader.fieldnames]
    for col in REQUIRED:
        if col not in headers:
            raise ChecklistError(f"必須列がありません: {col}")
    items = []
    seen_names = {}   # 点検内容 -> 何行目で出たか（重複検出用）
    seen_meters = {}  # (種別, メータ組) -> 何行目で出たか（使用前/使用後の重複検出用）
    order = 0
    for i, row in enumerate(reader):
        line = i + 2  # ヘッダ=1行目
        row = {(k.strip() if k else k): (v or "").strip() for k, v in row.items()}
        name = row.get("点検内容", "")
        if name == "":
            continue  # 空行スキップ
        if name in seen_names:
            raise ChecklistError(
                f"{line}行目: 点検内容『{name}』が重複しています"
                f"（{seen_names[name]}行目と同じ）。各行で異なる名前にしてください。"
            )
        seen_names[name] = line
        item_type = row.get("種別", "")
        if item_type not in VALID_TYPES:
            raise ChecklistError(f"{line}行目: 種別は check / number / meter / meter_before / meter_after / time / calc のいずれかにしてください（現在: '{item_type}'）")
        try:
            lo = _to_float(row.get("下限"))
            hi = _to_float(row.get("上限"))
        except ChecklistError as e:
            raise ChecklistError(f"{line}行目: {e}")
        if lo is not None and hi is not None and lo > hi:
            raise ChecklistError(f"{line}行目: 下限が上限より大きいです（{lo} > {hi}）")
        if item_type in ("meter_before", "meter_after"):
            group = row.get("メータ組", "")
            key = (item_type, group)
            if key in seen_meters:
                label = "使用前" if item_type == "meter_before" else "使用後"
                if group == "":
                    raise ChecklistError(
                        f"{line}行目: {label}の行が複数あり、「メータ組」が空です"
                        f"（{seen_meters[key]}行目と同じ）。組ごとに「メータ組」に異なる名前を入れてください。"
                    )
                raise ChecklistError(
                    f"{line}行目: {label}の行で「メータ組」『{group}』が重複しています"
                    f"（{seen_meters[key]}行目と同じ）。組ごとに異なる名前にしてください。"
                )
            seen_meters[key] = line
        items.append({
            "section": row.get("区分", ""),
            "item_name": name,
            "item_type": item_type,
            "unit": row.get("単位", ""),
            "min_value": lo,
            "max_value": hi,
            "remark": row.get("備考", ""),
            "important": bool(row.get("重要", "").strip()),  # 「重要」列が空でなければ注意点を赤字表示
            "meter_group": row.get("メータ組", "").strip(),  # 使用前/使用後の対応付けキー
            "formula": row.get("計算式", "").strip(),          # calc項目の計算式
            "sort_order": order,
        })
        order += 1
    if not items:
        raise ChecklistError("点検項目が1件もありません")
    return items

def judge(value, lo, hi):
    if value is None or (lo is None and hi is None):
        return ""
    if lo is not None and value < lo:
        return "NG"
    if hi is not None and value > hi:
        return "NG"
    return "OK"
