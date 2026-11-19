import json
import os

DEFAULTS = {"host": "127.0.0.1", "port": 5001, "debug": False}

def load_config(path="config.json"):
    cfg = dict(DEFAULTS)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    return cfg
