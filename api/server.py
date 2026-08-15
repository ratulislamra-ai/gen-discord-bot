import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import config.settings as settings
from api.routes import router as legacy_api_router
from api.routers.public import router as public_router
from api.routers.admin import router as admin_router
from api.auth import auth_router

def create_app() -> FastAPI:
    """Create and configure the FastAPI web application."""
    app = FastAPI(
        title="GEN Esports REST API & Tournament Platform Backend",
        description="REST API service providing tournament registration, team management, and match data for the GEN Esports website & Discord bot.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # Configure CORS middleware using CORS_ORIGINS from settings
    origins = settings.CORS_ORIGINS if settings.CORS_ORIGINS else ["http://localhost:3000"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files directory for team logos & media assets
    uploads_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

    # Mount website static assets (CSS, JS)
    website_dir = os.path.join(os.path.dirname(__file__), "..", "website")
    os.makedirs(website_dir, exist_ok=True)
    app.mount("/static", StaticFiles(directory=website_dir), name="static")

    # Serve GEN Esports Website Homepage
    @app.get("/", include_in_schema=False)
    async def serve_website_homepage():
        return FileResponse(os.path.join(website_dir, "index.html"))

    # Include API router modules
    app.include_router(legacy_api_router)
    app.include_router(public_router)
    app.include_router(admin_router)
    app.include_router(auth_router)

    return app

app = create_app()

async def run_api_server_async(host: str = "127.0.0.1", port: int = 8000):
    """
    Run uvicorn FastAPI server asynchronously inside the active asyncio loop.
    Allows Discord bot and FastAPI server to run concurrently without blocking.
    """
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()
