"""サンプル設備の様式PDF（form.pdf）と記入位置（mapping.json）を作り直す。

  .venv\\Scripts\\python.exe check\\tools\\make_sample_form.py

サンプル ボイラ・エアーコンプレッサーの2設備ぶんを上書きする。
自分の設備では、実際の様式PDFを置き、記入位置は画面（記入位置の設定）で決める。
"""
import json
import os

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

FONT = "HeiseiKakuGo-W5"
EQ_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "equipments")

X_LABEL, X_VALUE, X_UNIT, X_RIGHT = 60, 360, 470, 535
ROW_H = 24

# (見出し, [(欄の名前, 記入元, 単位, 追加設定), ...])
BOILER = ("ボイラ 日常点検記録表（サンプル様式）", [
    ("外観・始業確認", [
        ("本体に油漏れ・水漏れがない", "item:本体に油漏れ・水漏れがないこと", "", {"check_mark": "✓", "ng_color": "#ff0000"}),
        ("異音・異常振動がない", "item:異音・異常振動がないこと", "", {"check_mark": "✓", "ng_color": "#ff0000"}),
    ]),
    ("運転数値", [
        ("蒸気圧力（0.40〜0.60）", "item:蒸気圧力", "MPa", {"ng_color": "#ff0000"}),
        ("給水温度（60〜90）", "item:給水温度", "℃", {"ng_color": "#ff0000"}),
        ("排ガス温度", "item:排ガス温度", "℃", {}),
        ("装置起動時刻", "item:装置起動時刻", "", {}),
    ]),
    ("計量", [
        ("オイルメータ指示値", "item:オイルメータ指示値", "m3", {}),
        ("　同 当日使用量", "usage:オイルメータ指示値", "m3", {}),
        ("水道メータ指示値", "item:水道メータ指示値", "m3", {}),
        ("　同 当日使用量", "usage:水道メータ指示値", "m3", {}),
        ("オイル＋水道 使用量合計", "item:オイル＋水道 使用量合計", "m3", {}),
        ("オイル／水道 割合", "item:オイル／水道 割合(%)", "%", {}),
    ]),
    ("燃料", [
        ("燃料メータ（使用前）", "item:燃料メータ（使用前）", "L", {}),
        ("燃料メータ（使用後）", "item:燃料メータ（使用後）", "L", {}),
        ("燃料使用量", "ausage:燃料メータ（使用後）", "L", {}),
    ]),
])

COMPRESSOR = ("エアーコンプレッサー 日常点検記録表（サンプル様式）", [
    ("外観・始業確認", [
        ("本体に油漏れ・エア漏れがない", "item:本体に油漏れ・エア漏れがないこと", "", {"check_mark": "✓", "ng_color": "#ff0000"}),
        ("異音・異常振動がない", "item:異音・異常振動がないこと", "", {"check_mark": "✓", "ng_color": "#ff0000"}),
        ("冷却ファンが正常に回転している", "item:冷却ファンが正常に回転していること", "", {"check_mark": "✓", "ng_color": "#ff0000"}),
    ]),
    ("運転数値", [
        ("吐出圧力（0.70〜0.85）", "item:吐出圧力", "MPa", {"ng_color": "#ff0000"}),
        ("タンク内温度（60以下）", "item:タンク内温度", "℃", {"ng_color": "#ff0000"}),
        ("オイルレベル（30〜100）", "item:オイルレベル", "%", {"ng_color": "#ff0000"}),
    ]),
    ("定期作業", [
        ("ドレン排出を実施した", "item:ドレン排出を実施したこと", "", {"check_mark": "✓", "ng_color": "#ff0000"}),
    ]),
])


def make(key, spec):
    title, sections = spec
    d = os.path.join(EQ_DIR, key)
    c = canvas.Canvas(os.path.join(d, "form.pdf"), pagesize=A4)
    c.setTitle(title)
    c.setAuthor("")
    fields = []
    c.setFont(FONT, 15)
    c.drawCentredString(297, 790, title)
    c.setFont(FONT, 10)
    c.drawString(X_LABEL, 752, "点検日")
    c.line(X_LABEL + 40, 748, 280, 748)
    c.drawString(310, 752, "点検者")
    c.line(350, 748, X_RIGHT, 748)
    fields.append({"source": "meta.inspection_date", "page": 0, "x": X_LABEL + 48, "y": 752})
    fields.append({"source": "meta.inspector", "page": 0, "x": 358, "y": 752})

    y = 712
    for head, rows in sections:
        c.setFillGray(0.88)
        c.rect(X_LABEL, y - 6, X_RIGHT - X_LABEL, 20, stroke=0, fill=1)
        c.setFillGray(0)
        c.setFont(FONT, 10.5)
        c.drawString(X_LABEL + 6, y, f"■ {head}")
        y -= ROW_H
        c.setFont(FONT, 10)
        for label, source, unit, extra in rows:
            c.drawString(X_LABEL + 6, y, label)
            if unit:
                c.drawString(X_UNIT, y, unit)
            c.setStrokeGray(0.6)
            c.line(X_LABEL, y - 7, X_RIGHT, y - 7)
            c.setStrokeGray(0)
            fields.append({"source": source, "page": 0, "x": X_VALUE, "y": y, **extra})
            y -= ROW_H
        y -= 8

    c.drawString(X_LABEL, y, "特記事項")
    c.rect(X_LABEL, y - 90, X_RIGHT - X_LABEL, 82)
    fields.append({"source": "meta.note", "page": 0, "x": X_LABEL + 8, "y": y - 24})
    c.save()

    for f in fields:
        f.setdefault("font_size", 10)
        f.setdefault("color", "#000000")
    with open(os.path.join(d, "mapping.json"), "w", encoding="utf-8") as fp:
        json.dump({"default_font_size": 10, "fields": fields}, fp, ensure_ascii=False, indent=2)
    print("wrote", key, len(fields), "fields")


def main():
    pdfmetrics.registerFont(UnicodeCIDFont(FONT))
    make("sample_boiler", BOILER)
    make("air_compressor", COMPRESSOR)


if __name__ == "__main__":
    main()
