import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.routes import router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers

settings = get_settings()
app = FastAPI(title="FitDesi API", version="1.0.0", description="Pakistani fitness and nutrition API")
register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix=settings.api_prefix)


@app.get("/", response_class=HTMLResponse)
def home():
    page = Path(__file__).resolve().parents[2] / "public" / "index.html"
    if page.exists():
        return page.read_text(encoding="utf-8")
    return "<h1>FitDesi</h1><p><a href=\"/fitdesi.apk?v=3\">Download the Android app</a></p>"


apk_file = Path(__file__).resolve().parents[2] / "public" / "fitdesi.apk"
if apk_file.exists() and not os.environ.get("VERCEL"):

    @app.get("/fitdesi.apk", include_in_schema=False)
    def download_apk():
        return FileResponse(
            apk_file,
            media_type="application/vnd.android.package-archive",
            filename="fitdesi.apk",
        )


admin_dir = Path(__file__).resolve().parents[2] / "admin"
if admin_dir.exists():
    app.mount("/admin", StaticFiles(directory=admin_dir, html=True), name="admin")
