"""運転記録を、Excel出力と同じ体裁のPDFに変換する。

- レイアウトは excel_export と揃える（タイトル / 日付 / 見出し[時刻・作業内容] / 本文）
- 上部3行（タイトル・日付・見出し）は各ページ先頭で繰り返す
- 重要行は色付け（レベル1=黄, レベル2=ピンク）
- 列幅は Excel と同じピクセル換算（時刻130px, 作業内容500px → 1px=0.75pt）
- 右上の余白にページ番号「現在ページ / 全体ページ数」を表示する
"""
import io
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

_FONT = "HeiseiKakuGo-W5"
_font_ready = False

PX = 0.75  # 1px(96dpi) → pt(72dpi)
COL1_W = 130 * PX   # 時刻
COL2_W = 500 * PX   # 作業内容

HEADER_FILL = colors.HexColor("#EEEEEE")
IMPORTANT_FILL = colors.HexColor("#FFF2CC")   # level1: 黄
IMPORTANT_FILL2 = colors.HexColor("#FFD6E7")  # level2: ピンク

INVALID_FILENAME_CHARS = re.compile(r'[\\/?*\[\]:<>|"]')


def _ensure_font():
    global _font_ready
    if not _font_ready:
        pdfmetrics.registerFont(UnicodeCIDFont(_FONT))
        _font_ready = True


def _format_date_jp(iso_date: str) -> str:
    y, m, d = iso_date.split("-")
    return f"{int(y)}年{int(m)}月{int(d)}日"


def _para(text: str, style: ParagraphStyle) -> Paragraph:
    s = escape("" if text is None else str(text))
    s = s.replace("\n", "<br/>")
    return Paragraph(s, style)


class _NumberedCanvas(canvas.Canvas):
    """全ページ確定後に『現在 / 全体』のページ番号を右上余白へ描画する。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_states = []

    def showPage(self):
        self._saved_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_states)
        for state in self._saved_states:
            self.__dict__.update(state)
            self._draw_page_number(total)
            super().showPage()
        super().save()

    def _draw_page_number(self, total):
        self.setFont(_FONT, 9)
        w, h = self._pagesize
        self.drawRightString(w - 1.5 * cm, h - 1.0 * cm, f"{self._pageNumber} / {total}")


def _build_table(record: dict, entries: list[dict]) -> Table:
    title_style = ParagraphStyle("t", fontName=_FONT, fontSize=14, leading=18, alignment=TA_LEFT)
    date_style = ParagraphStyle("d", fontName=_FONT, fontSize=11, leading=14, alignment=TA_RIGHT)
    head_style = ParagraphStyle("h", fontName=_FONT, fontSize=11, leading=14, alignment=TA_CENTER)
    cell_style = ParagraphStyle("c", fontName=_FONT, fontSize=10.5, leading=14, alignment=TA_LEFT)

    data = [
        [_para(record.get("title") or "(無題)", title_style), ""],
        [_para(_format_date_jp(record["record_date"]), date_style), ""],
        [_para("時刻", head_style), _para("作業内容", head_style)],
    ]
    cmds = [
        ("SPAN", (0, 0), (1, 0)),                 # タイトル行を結合
        ("SPAN", (0, 1), (1, 1)),                 # 日付行を結合
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 2), (-1, 2), HEADER_FILL),   # 見出し行の背景
        ("GRID", (0, 2), (-1, -1), 0.5, colors.black),  # 見出し＋本文に罫線
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]

    row = 3
    for e in entries:
        data.append([_para(e.get("time_text", ""), cell_style),
                     _para(e.get("content", ""), cell_style)])
        lvl = e.get("is_important")
        if lvl == 1:
            cmds.append(("BACKGROUND", (0, row), (-1, row), IMPORTANT_FILL))
        elif lvl == 2:
            cmds.append(("BACKGROUND", (0, row), (-1, row), IMPORTANT_FILL2))
        row += 1
    if not entries:
        data.append([_para("", cell_style), _para("", cell_style)])

    t = Table(data, colWidths=[COL1_W, COL2_W], repeatRows=3)  # 上部3行を各ページで繰り返す
    t.setStyle(TableStyle(cmds))
    return t


def build_single_pdf(record: dict, entries: list[dict]) -> bytes:
    _ensure_font()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=1.5 * cm,   # 左余白2cm（Excelと同じ）
        topMargin=1.8 * cm, bottomMargin=1.5 * cm,
        title=str(record.get("title") or ""),
    )
    doc.build([_build_table(record, entries)], canvasmaker=_NumberedCanvas)
    return buf.getvalue()


def filename_for_single_pdf(record: dict) -> str:
    title = INVALID_FILENAME_CHARS.sub("_", record.get("title") or "")
    return f"運転記録_{record['record_date']}_{title}.pdf"
