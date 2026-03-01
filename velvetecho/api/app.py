"""
VelvetEcho API Application Factory

Clean, modular FastAPI application with auto-discovery of routers.
This file stays ~20 lines regardless of how many resources you add!
"""

from fastapi import FastAPI
from velvetecho.api.middleware import setup_middleware
from velvetecho.api.routers import discover_routers


def create_app() -> FastAPI:
    """
    Create FastAPI application with auto-discovered routers.

    This factory pattern keeps the app file clean and prevents
    it from becoming a monolithic file with hundreds of routes.

    To add a new resource:
    1. Create velvetecho/api/routers/your_resource.py
    2. Define 'router' variable and optional PREFIX/TAGS
    3. Done! Auto-discovery handles the rest.

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="VelvetEcho API",
        description="Enterprise-grade workflow orchestration platform",
        version="2.0.0",
    )

    # Setup middleware (logging, error handling, CORS, etc.)
    setup_middleware(app)

    # Auto-discover and mount all routers
    routers = discover_routers()
    for prefix, tags, router in routers:
        app.include_router(router, prefix=prefix, tags=tags)
        print(f"✅ Mounted router: {prefix} (tags: {tags})")

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "service": "velvetecho-api",
            "version": "2.0.0",
        }

    return app


# For development: uvicorn velvetecho.api.app:app --reload
app = create_app()
