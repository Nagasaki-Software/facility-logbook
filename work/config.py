import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    port: int = 6060
    polling_interval_seconds: int = 3
    backup_enabled: bool = True
    backup_keep_days: int = 90
    database_path: str = "records.db"
    backup_dir: str = "backup"
    upload_dir: str = "uploads"


def load_config(path: Path | str = "config.json") -> Config:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return Config(
        port=data.get("port", 6060),
        polling_interval_seconds=data.get("polling_interval_seconds", 3),
        backup_enabled=data.get("backup_enabled", True),
        backup_keep_days=data.get("backup_keep_days", 90),
        database_path=data.get("database_path", "records.db"),
        backup_dir=data.get("backup_dir", "backup"),
        upload_dir=data.get("upload_dir", "uploads"),
    )
