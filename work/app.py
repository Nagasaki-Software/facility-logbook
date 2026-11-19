from flask import Flask, g
from pathlib import Path
from .config import load_config
from .database import init_db, get_connection

DEFAULT_APP_TITLE = "運転記録"


def _load_app_title(app: Flask) -> str:
    # 設定で上書きされていればそれを使う（テスト用）
    if app.config.get("APP_TITLE"):
        return app.config["APP_TITLE"]
    # app.py と同じフォルダの app_title.txt を読む（UTF-8 / Shift-JIS どちらでも可）
    p = Path(app.root_path) / "app_title.txt"
    if p.exists():
        data = p.read_bytes()
        for enc in ("utf-8-sig", "cp932"):
            try:
                t = data.decode(enc).strip()
                if t:
                    return t
            except UnicodeDecodeError:
                continue
    return DEFAULT_APP_TITLE


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    cfg = load_config()
    app.config["DATABASE"] = cfg.database_path
    app.config["POLLING_INTERVAL"] = cfg.polling_interval_seconds
    app.config["PORT"] = cfg.port
    app.config["BACKUP_ENABLED"] = cfg.backup_enabled
    app.config["BACKUP_KEEP_DAYS"] = cfg.backup_keep_days
    app.config["BACKUP_DIR"] = cfg.backup_dir
    app.config["UPLOAD_DIR"] = cfg.upload_dir
    if overrides:
        app.config.update(overrides)

    @app.context_processor
    def _inject_app_title():
        # 配布先ごとに変えられるよう、app_title.txt からタイトルを読む（無ければ既定値）
        return {"app_title": _load_app_title(app)}

    @app.before_request
    def _open_db():
        g.db = get_connection(app.config["DATABASE"])

    @app.teardown_request
    def _close_db(exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    from .routes.pages import bp as pages_bp
    app.register_blueprint(pages_bp)

    from .routes.api_records import bp as api_records_bp
    app.register_blueprint(api_records_bp)

    from .routes.api_buttons import bp as api_buttons_bp
    app.register_blueprint(api_buttons_bp)

    from .routes.api_export import bp as api_export_bp
    app.register_blueprint(api_export_bp)

    from .routes.api_manual import bp as api_manual_bp
    app.register_blueprint(api_manual_bp)

    return app


if __name__ == "__main__":
    from .backup import start_backup_thread

    cfg = load_config()
    Path(cfg.database_path).touch(exist_ok=True)
    Path(cfg.upload_dir).mkdir(parents=True, exist_ok=True)
    init_db(cfg.database_path)
    app = create_app()
    if cfg.backup_enabled:
        start_backup_thread(
            Path(cfg.database_path),
            Path(cfg.backup_dir),
            keep_days=cfg.backup_keep_days,
        )
    app.run(host="0.0.0.0", port=app.config["PORT"])
