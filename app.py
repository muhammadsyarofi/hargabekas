"""
Aplikasi Utama HargaBekas — Sistem Prediksi Harga Motor & Mobil Bekas.
Menggunakan arsitektur modular Flask (routes/, models/, templates/, static/).
"""

import os
from flask import Flask
from models.database import init_db
from models.predictor import ensure_model_loaded
from routes.api import api_bp
from routes.web import web_bp


def create_app() -> Flask:
    """Factory function untuk menginisialisasi aplikasi Flask HargaBekas."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "hargabekas-editorial-secret-2025")
    app.config["JSON_AS_ASCII"] = False

    # Pastikan database SQLite dan model Machine Learning siap saat startup
    with app.app_context():
        ensure_model_loaded()
        init_db()

    # Registrasi Blueprints
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)

    # Filter Jinja2 untuk memformat mata uang Rupiah dan angka ribuan
    @app.template_filter("rupiah")
    def format_rupiah(value):
        try:
            num = int(round(float(value)))
            return f"Rp {num:,.0f}".replace(",", ".")
        except (ValueError, TypeError):
            return "Rp 0"

    @app.template_filter("ribuan")
    def format_ribuan(value):
        try:
            num = int(round(float(value)))
            return f"{num:,.0f}".replace(",", ".")
        except (ValueError, TypeError):
            return "0"

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
