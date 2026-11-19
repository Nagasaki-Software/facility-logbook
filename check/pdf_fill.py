import io
import json
import os
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.colors import red, black, HexColor
from pypdf import PdfReader, PdfWriter
from .numfmt import fmt_num

_FONT = "HeiseiKakuGo-W5"
_font_ready = False

# チェックマーク用フォント（Segoe UI Symbol は Windows 8/10/11 標準搭載）
_CHECK_FONT = "SegoeUISymbol"
_check_font_ready = False
_CHECK_CHARS = frozenset(["✓", "✔", "☑"])  # これらの文字は専用フォントで描画
_CHECK_FONT_PATH = r"C:\Windows\Fonts\seguisym.ttf"

def _ensure_font():
    global _font_ready
    if not _font_ready:
        pdfmetrics.registerFont(UnicodeCIDFont(_FONT))
        _font_ready = True

def _ensure_check_font():
    """チェックマーク用フォントを登録する。失敗したら False を返す。"""
    global _check_font_ready
    if _check_font_ready:
        return True
    if not os.path.exists(_CHECK_FONT_PATH):
        return False
    try:
        from reportlab.pdfbase.ttfonts import TTFont
        pdfmetrics.registerFont(TTFont(_CHECK_FONT, _CHECK_FONT_PATH))
        _check_font_ready = True
        return True
    except Exception:
        return False

def _index_items(detail):
    idx = {}
    for it in detail.get("items", []):
        idx[it["item_name"]] = it
    return idx

_fmt_num = fmt_num  # 表示用の数値整形は check/numfmt.py に一本化

def _parse_color(val, default):
    if not val:
        return default
    if isinstance(val, str):
        if val.lower() == "red":
            return red
        if val.startswith("#"):
            try:
                return HexColor(val)
            except Exception:
                return default
    return default

def _value_for(source, detail, items, field):
    if source.startswith("meta."):
        return detail.get(source.split(".", 1)[1], ""), "OK"
    if source.startswith("usage:"):
        # 1行方式メータの当日使用量（api_pdf 側で detail["meter_usage"] に格納）
        name = source.split(":", 1)[1]
        val = (detail.get("meter_usage") or {}).get(name)
        return ("" if val is None else _fmt_num(val)), ""
    if source.startswith("ausage:"):
        # 行分け方式メータの当日使用量（使用後の行名で指定）。同じメータ組の使用前と差を取る。
        name = source.split(":", 1)[1]
        after_it = items.get(name)
        if after_it is None or after_it.get("item_type") != "meter_after":
            return "", ""
        grp = after_it.get("meter_group") or ""
        after = after_it.get("value_number")
        before = None
        for it in items.values():
            if it.get("item_type") == "meter_before" and (it.get("meter_group") or "") == grp:
                before = it.get("value_number")
                break
        if after is None or before is None or after < before:
            return "", ""
        return _fmt_num(after - before), ""
    if source.startswith("gusage:"):
        # 旧方式（メータ組で指定）。既に配置済みの様式があっても印字できるよう互換で残す。
        grp = source.split(":", 1)[1]
        before = after = None
        for it in items.values():
            if (it.get("meter_group") or "") != grp:
                continue
            if it.get("item_type") == "meter_before":
                before = it.get("value_number")
            elif it.get("item_type") == "meter_after":
                after = it.get("value_number")
        if before is None or after is None or after < before:
            return "", ""
        return _fmt_num(after - before), ""
    if source.startswith("item:"):
        name = source.split(":", 1)[1]
        it = items.get(name)
        if it is None:
            return "", ""
        if it.get("item_type") == "check":
            j = it.get("judgement", "")
            if it.get("value_check"):
                return field.get("check_mark", "✓"), j
            if j == "NG":
                return field.get("ng_mark", "×"), j   # NGのチェック項目は×（ng_color指定時は赤）で表示
            return "", j
        if it.get("item_type") == "time":
            return (it.get("value_text") or ""), ""
        v = it.get("value_number")
        return ("" if v is None else _fmt_num(v)), it.get("judgement", "")
    return "", ""

def fill_pdf(form_path, mapping_path, detail, out_path):
    if not os.path.exists(form_path):
        raise FileNotFoundError(f"様式PDFがありません: {form_path}")
    if not os.path.exists(mapping_path):
        raise FileNotFoundError(f"座標マッピングファイルがありません: {mapping_path}")
    _ensure_font()
    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)
    default_size = mapping.get("default_font_size", 10)
    items = _index_items(detail)

    overlays = {}
    for field in mapping.get("fields", []):
        overlays.setdefault(field.get("page", 0), []).append(field)

    writer = PdfWriter()
    writer.append(form_path)  # clone pages into writer so merge targets attached pages

    for pno, page in enumerate(writer.pages):
        fields = overlays.get(pno)
        if not fields:
            continue
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(w, h))
        drawn = 0
        for field in fields:
            source = field.get("source", "")
            x = field.get("x")
            y = field.get("y")
            if not source or x is None or y is None:
                continue
            text, judgement = _value_for(source, detail, items, field)
            if text == "":
                continue
            size = field.get("font_size", default_size)
            base = _parse_color(field.get("color"), black)
            if field.get("ng_color") and judgement == "NG":
                c.setFillColor(_parse_color(field.get("ng_color"), red))
            else:
                c.setFillColor(base)
            # チェックマーク文字は専用フォントで描画（✓ が見えないフォント問題の回避）
            if str(text) in _CHECK_CHARS and _ensure_check_font():
                c.setFont(_CHECK_FONT, size)
            else:
                c.setFont(_FONT, size)
            c.drawString(x, y, str(text))
            drawn += 1
        if drawn == 0:
            continue
        c.save()
        buf.seek(0)
        overlay_page = PdfReader(buf).pages[0]
        page.merge_page(overlay_page)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        writer.write(f)
    return out_path


def fill_pdf_multi(form_path, mapping_path, details, out_path):
    """複数の点検データを1つのPDFに連結して出力する（各点検ごとに様式1部）"""
    if not details:
        raise ValueError("出力対象の点検データがありません")
    if not os.path.exists(form_path):
        raise FileNotFoundError(f"様式PDFがありません: {form_path}")
    if not os.path.exists(mapping_path):
        raise FileNotFoundError(f"座標マッピングファイルがありません: {mapping_path}")
    _ensure_font()
    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)
    default_size = mapping.get("default_font_size", 10)

    # ページ番号→フィールドリスト のテンプレを一度だけ構築
    overlays_tmpl = {}
    for field in mapping.get("fields", []):
        overlays_tmpl.setdefault(field.get("page", 0), []).append(field)

    combined = PdfWriter()
    for detail in details:
        items = _index_items(detail)
        # 様式PDFを毎回新規に読み込み（ページ参照を独立させるため）
        per = PdfWriter()
        per.append(form_path)
        for pno, page in enumerate(per.pages):
            fields = overlays_tmpl.get(pno)
            if fields:
                w = float(page.mediabox.width)
                h = float(page.mediabox.height)
                buf = io.BytesIO()
                c = canvas.Canvas(buf, pagesize=(w, h))
                drawn = 0
                for field in fields:
                    source = field.get("source", "")
                    x = field.get("x")
                    y = field.get("y")
                    if not source or x is None or y is None:
                        continue
                    text, judgement = _value_for(source, detail, items, field)
                    if text == "":
                        continue
                    size = field.get("font_size", default_size)
                    base = _parse_color(field.get("color"), black)
                    if field.get("ng_color") and judgement == "NG":
                        c.setFillColor(_parse_color(field.get("ng_color"), red))
                    else:
                        c.setFillColor(base)
                    if str(text) in _CHECK_CHARS and _ensure_check_font():
                        c.setFont(_CHECK_FONT, size)
                    else:
                        c.setFont(_FONT, size)
                    c.drawString(x, y, str(text))
                    drawn += 1
                if drawn > 0:
                    c.save()
                    buf.seek(0)
                    overlay_page = PdfReader(buf).pages[0]
                    page.merge_page(overlay_page)
            combined.add_page(page)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        combined.write(f)
    return out_path
