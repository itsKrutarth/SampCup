from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_security_headers_on_api_responses(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "content-security-policy" not in client.get("/api/docs").headers


@pytest.fixture
def site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<title>SAMP Cup</title>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    (tmp_path.parent / "secret.txt").write_text("nope")
    monkeypatch.setenv("STATIC_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        yield TestClient(create_app())
    finally:
        get_settings.cache_clear()


def test_serves_the_built_frontend(site: TestClient) -> None:
    asset = site.get("/assets/app.js")
    assert asset.text == "console.log(1)" and "immutable" in asset.headers["cache-control"]
    assert site.get("/favicon.svg").headers["cache-control"] == "no-cache"
    for path in ("/", "/standings", "/admin/teams"):  # client-side routes
        assert "SAMP Cup" in site.get(path).text
    assert "SAMP Cup" in site.get("/..%2Fsecret.txt").text  # never leaves the folder
    assert site.get("/api/nothing-here").status_code == 404
