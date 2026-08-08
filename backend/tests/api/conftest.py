from importlib import import_module

import pytest


def _flatten_app_routes(app):
    """Return concrete routes from FastAPI's included-router wrappers."""
    flattened_routes = []
    for route in app.router.routes:
        original_router = getattr(route, "original_router", None)
        if original_router is None:
            flattened_routes.append(route)
            continue

        for original_route in original_router.routes:
            if hasattr(original_route, "dependency_overrides_provider"):
                original_route.dependency_overrides_provider = app
            flattened_routes.append(original_route)

    return flattened_routes


@pytest.fixture
def main_module(monkeypatch):
    monkeypatch.setenv("POSTGRES_DB", "test_db")
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")

    module = import_module("compliance.api.main")
    module.flat_routes = _flatten_app_routes(module.app)
    return module
