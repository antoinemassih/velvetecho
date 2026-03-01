"""
API Routers Package

Auto-discovery of routers for modular API organization.
Each router file represents one domain/resource.
"""

from pathlib import Path
from typing import List
from fastapi import APIRouter
import importlib
import inspect


def discover_routers() -> List[tuple[str, APIRouter]]:
    """
    Auto-discover all routers in this package.

    Returns:
        List of (prefix, router) tuples

    Example:
        routers = discover_routers()
        for prefix, router in routers:
            app.include_router(router, prefix=prefix)
    """
    routers = []
    router_dir = Path(__file__).parent

    # Scan all .py files except __init__.py
    for file_path in router_dir.glob("*.py"):
        if file_path.name.startswith("_"):
            continue

        # Import module
        module_name = f"velvetecho.api.routers.{file_path.stem}"
        try:
            module = importlib.import_module(module_name)

            # Look for 'router' variable
            if hasattr(module, "router") and isinstance(module.router, APIRouter):
                router = module.router

                # Get prefix from module or use default
                prefix = getattr(module, "PREFIX", f"/api/{file_path.stem}")
                tags = getattr(module, "TAGS", [file_path.stem.title()])

                routers.append((prefix, tags, router))

        except Exception as e:
            print(f"Warning: Could not load router from {module_name}: {e}")

    return routers


__all__ = ["discover_routers"]
