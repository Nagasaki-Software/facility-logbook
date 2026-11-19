import math
import re
import unicodedata
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet


MEIRYO = "Meiryo"

# ── レイアウト指定（ピクセル）──────────────────────────────
COL1_PX = 130          # 1列目（時刻）の幅
COL2_PX = 500          # 2列目（作業内容）の幅
TITLE_ROW_PX = 40      # 2行目(日付)・3行目(見出し)の高さ
BODY_BASE_PX = 40      # 運転記録1行ぶんの高さ
BODY_STEP_PX = 20      # 1行増えるごとに足す高さ
LEFT_MARGIN_CM = 2.0   # 左余白


def _px_to_col_width(px: float) -> float:
    """ピクセル → Excel列幅。Excelのピクセル表示は (列幅 × 7) なので px/7 とする
    （例: 幅12→84px、幅60→420px。逆に 130px→幅18.57、500px→幅71.43）。"""
    return max(0.0, px / 7.0)


def _px_to_row_height(px: float) -> float:
    """ピクセル(96dpi) → 行高さ(ポイント, 72dpi)。"""
    return px * 0.75


# 2列目の幅から「1行に入るおおよその文字量（半角換算）」を求める
# （全角を2・半角を1として数え、Meiryo 11pt の半角幅 ≒ 7.3px、左右パディング約8pxを考慮）
_UNITS_PER_LINE = max(1, int((COL2_PX - 8) / 7.3))


def _estimate_lines(text) -> int:
    """セル内で何行に折り返すかを推定する（改行＋文字数からの概算）。"""
    if text is None or str(text).strip() == "":
        return 1
    total = 0
    for seg in str(text).split("\n"):
        units = 0
        for ch in seg:
            units += 2 if unicodedata.east_asian_width(ch) in ("W", "F", "A") else 1
        total += max(1, math.ceil(units / _UNITS_PER_LINE))
    return max(1, total)
IMPORTANT_FILL = PatternFill("solid", fgColor="FFFFF2CC")    # level1: 黄
IMPORTANT_FILL2 = PatternFill("solid", fgColor="FFFFD6E7")   # level2: ピンク
HEADER_FILL = PatternFill("solid", fgColor="FFEEEEEE")
THIN = Side(border_style="thin", color="FF000000")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
INVALID_SHEET_CHARS = re.compile(r'[\\/?*\[\]:]')
INVALID_FILENAME_CHARS = re.compile(r'[\\/?*\[\]:<>|"]')


def _sheet_name(record: dict) -> str:
    base = f"{record['record_date']}_{record['title']}".strip("_")
    base = INVALID_SHEET_CHARS.sub("_", base)
    return base[:31] or "sheet"


def _format_date_jp(iso_date: str) -> str:
    y, m, d = iso_date.split("-")
    return f"{int(y)}年{int(m)}月{int(d)}日"


def _build_sheet(ws: Worksheet, record: dict, entries: list[dict]) -> None:
    ws.title = _sheet_name(record)

    # Row 1: title (left). タイトルだけで1行使い、長くても切れないようにする
    ws["A1"] = record["title"]
    ws["A1"].font = Font(name=MEIRYO, size=14, bold=True)
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")

    # Row 2: date (right side = 作業内容列の右端)
    ws["B2"] = _format_date_jp(record["record_date"])
    ws["B2"].font = Font(name=MEIRYO, size=11)
    ws["B2"].alignment = Alignment(horizontal="right", vertical="center")
    ws.row_dimensions[2].height = _px_to_row_height(TITLE_ROW_PX)

    # Row 3: column headings
    ws["A3"] = "時刻"
    ws["B3"] = "作業内容"
    for cell in (ws["A3"], ws["B3"]):
        cell.font = Font(name=MEIRYO, size=11, bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.fill = HEADER_FILL
        cell.border = BORDER
    ws.row_dimensions[3].height = _px_to_row_height(TITLE_ROW_PX)

    # Body rows (start at row 4)
    for i, e in enumerate(entries, start=4):
        a = ws.cell(row=i, column=1, value=e["time_text"])
        b = ws.cell(row=i, column=2, value=e["content"])
        a.font = Font(name=MEIRYO, size=11)
        b.font = Font(name=MEIRYO, size=11)
        a.alignment = Alignment(horizontal="left", vertical="center")
        b.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        a.border = BORDER
        b.border = BORDER
        lvl = e.get("is_important")
        fill = IMPORTANT_FILL if lvl == 1 else (IMPORTANT_FILL2 if lvl == 2 else None)
        if fill:
            a.fill = fill
            b.fill = fill
        # 運転記録の行数に応じて高さを可変（1行=40px, 以降 +20px/行）
        lines = _estimate_lines(e["content"])
        ws.row_dimensions[i].height = _px_to_row_height(BODY_BASE_PX + (lines - 1) * BODY_STEP_PX)

    # Column widths
    ws.column_dimensions[get_column_letter(1)].width = _px_to_col_width(COL1_PX)
    ws.column_dimensions[get_column_letter(2)].width = _px_to_col_width(COL2_PX)

    # 上部3行を印刷タイトル行に（各ページ上部で繰り返す）
    ws.print_title_rows = "1:3"

    # Page setup
    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins.left = LEFT_MARGIN_CM / 2.54  # 2cm → インチ
    ws.page_margins.right = 0.59
    ws.page_margins.top = 0.59
    ws.page_margins.bottom = 0.59


def build_single_workbook(record: dict, entries: list[dict]) -> Workbook:
    wb = Workbook()
    _build_sheet(wb.active, record, entries)
    return wb


def build_multi_workbook(records_with_entries: list[tuple[dict, list[dict]]]) -> Workbook:
    wb = Workbook()
    wb.remove(wb.active)
    for rec, entries in sorted(records_with_entries, key=lambda x: x[0]["record_date"]):
        ws = wb.create_sheet()
        _build_sheet(ws, rec, entries)
    return wb


def filename_for_single(record: dict) -> str:
    title = INVALID_FILENAME_CHARS.sub("_", record["title"])
    return f"運転記録_{record['record_date']}_{title}.xlsx"


def filename_for_range(start_date: str, end_date: str) -> str:
    return f"運転記録_{start_date}_to_{end_date}.xlsx"
