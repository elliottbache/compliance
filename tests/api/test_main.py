def test_app_registers_expected_router_prefixes(main_module):
    """Verify the FastAPI app includes the public API router prefixes."""
    paths = {getattr(route, "path", "") for route in main_module.app.routes}

    assert any(path.startswith("/sites") for path in paths)
    assert any(path.startswith("/certifications") for path in paths)
    assert any(path.startswith("/attachments") for path in paths)
    assert any(path.startswith("/findings") for path in paths)
    assert any(path.startswith("/clients") for path in paths)
    assert any(path.startswith("/certifiers") for path in paths)
    assert any(path.startswith("/rules") for path in paths)
    assert any(path.startswith("/regulations") for path in paths)
