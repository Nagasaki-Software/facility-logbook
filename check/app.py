from flask import Flask
from .config import load_config
from .database import init_db

def _load_title(path="title.txt"):
    default = "設備運転 点検チェックリスト"
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return default
    # UTF-8（BOM付き可）/ Shift-JIS どちらでも可
    for enc in ("utf-8-sig", "cp932"):
        try:
            t = data.decode(enc).strip()
            return t if t else default
        except UnicodeDecodeError:
            continue
    return default

def create_app(overrides=None):
    overrides = overrides or {}
    app = Flask(__name__)
    # テンプレートの変更をサーバー再起動なしで反映する
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.auto_reload = True
    app.config["DB_PATH"] = overrides.get("db_path", "records.db")
    app.config["EQUIPMENTS_DIR"] = overrides.get("equipments_dir", "equipments")
    app.config["OUTPUT_DIR"] = overrides.get("output_dir", "output")
    app.config["APP_TITLE"] = _load_title(overrides.get("title_file", "title.txt"))
    app.config["INSPECTORS_CSV"] = overrides.get("inspectors_csv", "inspectors.csv")
    app.config["CONFIG_JSON"] = overrides.get("config_json", "config.json")

    from .routes.pages import pages_bp
    app.register_blueprint(pages_bp)

    from .routes.api_inspections import api_inspections_bp
    from .routes.api_pdf import api_pdf_bp
    app.register_blueprint(api_inspections_bp)
    app.register_blueprint(api_pdf_bp)

    from .routes.layout import layout_bp
    app.register_blueprint(layout_bp)
    return app

if __name__ == "__main__":
    cfg = load_config()
    init_db("records.db")
    application = create_app()
    application.run(host=cfg["host"], port=cfg["port"], debug=cfg["debug"])
