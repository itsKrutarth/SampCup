import json
import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api import public
from app.core.config import get_settings
from app.main import create_app
from app.store import Store, get_store


def test_headers_on_api_responses(client: TestClient) -> None:
    response = client.get("/api/public/teams")
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "public, max-age=0, s-maxage=3"
    assert client.get("/api/health").headers["cache-control"] == "no-store"
    assert client.get("/api/public/teams/99").headers["cache-control"] == "no-store"
    assert "content-security-policy" not in client.get("/api/docs").headers


def test_every_request_is_logged_as_json(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    logger = logging.getLogger("sampcup")
    logger.addHandler(caplog.handler)
    try:
        client.get("/api/health")
    finally:
        logger.removeHandler(caplog.handler)
    line = json.loads(caplog.records[-1].getMessage())
    assert line["path"] == "/api/health" and line["status"] == 200 and "ms" in line


def test_unexpected_errors_become_a_logged_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(public, "get_tournament", broken)
    response = client.get("/api/public/overview")
    assert response.status_code == 500
    assert response.json() == {"detail": "Something went wrong. Please try again."}


@pytest.fixture
def behind_cloudfront(store: Store, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("ORIGIN_SECRET", "edge-secret")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_store] = lambda: store
    try:
        yield TestClient(app)
    finally:
        get_settings.cache_clear()


def test_only_cloudfront_may_call_the_function(behind_cloudfront: TestClient) -> None:
    assert behind_cloudfront.get("/api/health").status_code == 403
    assert (
        behind_cloudfront.get("/api/health", headers={"x-origin-verify": "wrong"}).status_code
        == 403
    )
    assert (
        behind_cloudfront.get("/api/health", headers={"x-origin-verify": "edge-secret"}).status_code
        == 200
    )


def test_rate_limits_use_the_visitor_address_cloudfront_reports(
    behind_cloudfront: TestClient,
) -> None:
    headers = {"x-origin-verify": "edge-secret", "x-forwarded-for": "6.6.6.6, 1.2.3.4, 130.176.0.1"}
    body = {"team_name": "x", "password": "y"}
    codes = [
        behind_cloudfront.post("/api/auth/team-login", json=body, headers=headers).status_code
        for _ in range(11)
    ]
    assert codes[-1] == 429
    other = {**headers, "x-forwarded-for": "5.6.7.8, 130.176.0.1"}
    assert (
        behind_cloudfront.post("/api/auth/team-login", json=body, headers=other).status_code == 401
    )
    single = {**headers, "x-forwarded-for": "9.9.9.9"}
    assert (
        behind_cloudfront.post("/api/auth/team-login", json=body, headers=single).status_code == 401
    )


def test_lambda_handler_serves_a_function_url_event(store: Store) -> None:
    from app.lambda_handler import app as lambda_app
    from app.lambda_handler import handler

    lambda_app.dependency_overrides[get_store] = lambda: store
    event = {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": "/api/ready",
        "rawQueryString": "",
        "headers": {"host": "example.lambda-url.us-east-1.on.aws"},
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/api/ready",
                "protocol": "HTTP/1.1",
                "sourceIp": "1.2.3.4",
                "userAgent": "test",
            },
            "requestId": "r1",
            "stage": "$default",
        },
        "isBase64Encoded": False,
    }
    try:
        result = handler(event, type("Context", (), {"aws_request_id": "r1"})())
    finally:
        lambda_app.dependency_overrides.clear()
    assert result["statusCode"] == 200 and json.loads(result["body"]) == {"status": "ready"}
