from flask import Flask, send_from_directory
from .db import init_db
from .i18n import i18n_bp
from .routes.auth_routes import auth_bp
from .routes.inventory_routes import inventory_bp
from .routes.settings_routes import settings_bp
from .routes.report_routes import report_bp
from .routes.staff_routes import staff_bp

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.secret_key = "storagecheck_v2_secret_change_me"

    # Allow larger uploads (banner file upload).
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB

    init_db(app)

    app.register_blueprint(i18n_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(staff_bp)

    # Serve files from instance/ (e.g. instance/uploads/banner.jpg)
    @app.get("/instance/<path:filename>")
    def instance_files(filename):
        return send_from_directory(app.instance_path, filename)

    return app