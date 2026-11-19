import json
import os
import re
from .csv_loader import load_checklist

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

META_FIELDS = [
    ("meta.inspection_date", "点検日"),
    ("meta.inspector", "点検者"),
    ("meta.note", "特記事項"),
]

class LayoutError(Exception):
    pass

def _to_int(v, default):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default

def _norm_color(val, default=None):
    if val is None or val == "":
        return default
    if isinstance(val, str):
        if val.lower() == "red":
            return "#ff0000"
        if _HEX_RE.match(val):
            return val
    return default

def _load_mapping(mapping_path):
    if mapping_path and os.path.exists(mapping_path):
        with open(mapping_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"default_font_size": 11, "fields": []}

def build_fields(equipment):
    mapping = _load_mapping(equipment["mapping_path"])
    default_fs = mapping.get("default_font_size", 11)
    by_source = {f["source"]: f for f in mapping.get("fields", []) if f.get("source")}

    items = load_checklist(equipment["csv_path"])  # may raise ChecklistError
    known = [(s, label, "meta") for s, label in META_FIELDS]
    for it in items:
        known.append((f"item:{it['item_name']}", it["item_name"], it["item_type"]))
        # 1行方式メータ：アプリ計算の「当日使用量」も配置できるようにする
        if it["item_type"] == "meter":
            known.append((f"usage:{it['item_name']}", f"{it['item_name']}（当日使用量）", "usage"))
        # 行分け方式メータ：使用後の行ごとに「当日使用量」を配置できるようにする（メータ組の有無を問わない）
        if it["item_type"] == "meter_after":
            known.append((f"ausage:{it['item_name']}", f"{it['item_name']}（当日使用量）", "usage"))
    known_sources = {s for s, _, _ in known}

    def entry_from_mapping(src, label, kind, m, orphan=False):
        return {
            "source": src, "label": label, "kind": kind,
            "placed": (m.get("x") is not None and m.get("y") is not None),
            "orphan": orphan,
            "page": m.get("page", 0), "x": m.get("x"), "y": m.get("y"),
            "font_size": _to_int(m.get("font_size", default_fs), default_fs),
            "color": _norm_color(m.get("color"), "#000000"),
            "ng_color": _norm_color(m.get("ng_color"), None),
        }

    fields = []
    for src, label, kind in known:
        m = by_source.get(src)
        if m is not None:
            fields.append(entry_from_mapping(src, label, kind, m))
        else:
            fields.append({
                "source": src, "label": label, "kind": kind,
                "placed": False, "orphan": False,
                "page": 0, "x": None, "y": None,
                "font_size": default_fs, "color": "#000000", "ng_color": None,
            })
    for src, m in by_source.items():
        if src not in known_sources:
            label = src.split(":", 1)[-1] if src and ":" in src else (src or "?")
            fields.append(entry_from_mapping(src, label, "orphan", m, orphan=True))

    return {"default_font_size": default_fs, "fields": fields}

def save_layout(mapping_path, fields, deletes, page_sizes, default_font_size=11):
    mapping = _load_mapping(mapping_path)
    mapping.setdefault("default_font_size", default_font_size)
    by_source = {f["source"]: f for f in mapping.get("fields", []) if f.get("source")}

    for fld in fields:
        src = fld.get("source")
        if not src:
            continue
        page = int(fld.get("page", 0))
        if page not in page_sizes:
            raise LayoutError(f"ページ {page} のサイズが不明です")
        w_pt, h_pt = page_sizes[page]
        try:
            nx = float(fld["nx"]); ny = float(fld["ny"])
        except (KeyError, TypeError, ValueError):
            raise LayoutError(f"座標が不正です: {src}")
        if not (0.0 <= nx <= 1.0 and 0.0 <= ny <= 1.0):
            raise LayoutError(f"座標が範囲外です: {src}")
        entry = by_source.get(src, {"source": src})
        entry["page"] = page
        entry["x"] = round(nx * w_pt, 1)
        entry["y"] = round((1.0 - ny) * h_pt, 1)
        if fld.get("font_size") is not None:
            try:
                entry["font_size"] = int(fld["font_size"])
            except (TypeError, ValueError):
                raise LayoutError(f"文字サイズが不正です: {src}")
        if fld.get("color"):
            entry["color"] = fld["color"]
        if "ng_color" in fld:
            if fld["ng_color"]:
                entry["ng_color"] = fld["ng_color"]
            else:
                entry.pop("ng_color", None)
        by_source[src] = entry

    for src in (deletes or []):
        by_source.pop(src, None)

    mapping["fields"] = list(by_source.values())
    tmp = mapping_path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, mapping_path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
