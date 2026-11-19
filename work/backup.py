import re
import shutil
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

NAME_RE = re.compile(r"(?:records|check)_(\d{4})-(\d{2})-(\d{2})\.db$")


def perform_backup(src: Path, dest_dir: Path, *, today: datetime | None = None,
                   prefix: str = "records") -> Path:
    today = today or datetime.now()
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / f"{prefix}_{today.strftime('%Y-%m-%d')}.db"
    shutil.copy2(src, target)
    return target


def prune_old_backups(dest_dir: Path, *, keep_days: int, today: datetime | None = None) -> None:
    # Files dated strictly before (today - keep_days) are deleted; the cutoff date itself is retained.
    today = today or datetime.now()
    cutoff = today - timedelta(days=keep_days)
    if not dest_dir.exists():
        return
    for p in dest_dir.iterdir():
        m = NAME_RE.match(p.name)
        if not m:
            continue
        y, mo, d = map(int, m.groups())
        if datetime(y, mo, d) < cutoff:
            p.unlink()


def start_backup_thread(
    src: Path, dest_dir: Path, *, keep_days: int, interval_seconds: int = 3600,
    extra: tuple = ()
) -> threading.Thread:
    """Run backup once at startup, then every `interval_seconds`. Daemon thread.
    `extra` は (DBパス, ファイル名の接頭辞) の組。存在しないDBは黙ってスキップする。
    1つのDBの失敗が他のDBのバックアップを止めないよう、個別に実行する。"""
    def _loop():
        last_day = None
        while True:
            now = datetime.now()
            if now.date() != last_day:
                ok = True
                for s, prefix in ((src, "records"), *extra):
                    if prefix != "records" and not Path(s).exists():
                        continue
                    try:
                        perform_backup(s, dest_dir, today=now, prefix=prefix)
                    except Exception as e:
                        ok = False
                        print(f"[backup] {prefix} failed: {e}", file=sys.stderr)
                try:
                    prune_old_backups(dest_dir, keep_days=keep_days, today=now)
                except Exception as e:
                    ok = False
                    print(f"[backup] prune failed: {e}", file=sys.stderr)
                if ok:
                    last_day = now.date()
            time.sleep(interval_seconds)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return t
