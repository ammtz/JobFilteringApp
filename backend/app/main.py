from __future__ import annotations

from pathlib import Path

from flask import Flask, send_from_directory
from flask_cors import CORS

from app.api.v1 import cull as v1_cull
from app.api.v1 import jobs as v1_jobs
from app.api.v1 import preferences as v1_preferences
from app.api.v1 import sort as v1_sort

# Frontend: repo root is backend's parent
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR) if FRONTEND_DIR.exists() else None,
    static_url_path="",
)

CORS(app)

app.register_blueprint(v1_jobs.bp, url_prefix="/api/v1")
app.register_blueprint(v1_cull.bp, url_prefix="/api/v1")
app.register_blueprint(v1_preferences.bp, url_prefix="/api/v1")
app.register_blueprint(v1_sort.bp, url_prefix="/api/v1")


@app.get("/")
def index():
    return send_from_directory(str(FRONTEND_DIR), "index.html")


@app.get("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    from app.core.config import settings

    app.run(host=settings.API_HOST, port=settings.API_PORT, debug=settings.DEBUG)
