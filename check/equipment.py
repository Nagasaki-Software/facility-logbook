import json
import os

EQUIPMENTS_DIR = "equipments"

class EquipmentError(Exception):
    pass

def _load_one(folder):
    cfg_path = os.path.join(folder, "equipment.json")
    if not os.path.exists(cfg_path):
        return None
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    cfg.setdefault("key", os.path.basename(folder))
    cfg["dir"] = folder
    cfg["csv_path"] = os.path.join(folder, cfg.get("csv", "checklist.csv"))
    cfg["pdf_form_path"] = os.path.join(folder, cfg.get("pdf_form", "form.pdf"))
    cfg["mapping_path"] = os.path.join(folder, cfg.get("mapping", "mapping.json"))
    cfg.setdefault("order", 999)
    return cfg

def list_equipments(root=EQUIPMENTS_DIR):
    if not os.path.isdir(root):
        return []
    result = []
    for entry in sorted(os.listdir(root)):
        folder = os.path.join(root, entry)
        if os.path.isdir(folder):
            cfg = _load_one(folder)
            if cfg:
                result.append(cfg)
    result.sort(key=lambda c: (c.get("order", 999), c.get("key", "")))
    return result

def get_equipment(key, root=EQUIPMENTS_DIR):
    for eq in list_equipments(root):
        if eq.get("key") == key:
            return eq
    raise EquipmentError(f"設備が見つかりません: {key}")
