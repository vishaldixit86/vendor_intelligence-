"""Tests for the API health endpoint."""

from fastapi.testclient import TestClient

from app.main import app


def test_given_api_when_health_checked_then_returns_service_status() -> None:
    """The health route reports that the API is available."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.get("/api/health")

    # Assert
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "vendor-decision-intelligence",
    }


def test_given_vite_origin_when_cors_preflight_checked_then_allows_local_dashboard() -> None:
    """The API permits browser calls from the local Vite development server."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.options(
        "/api/health",
        headers={
            "Access-Control-Request-Method": "GET",
            "Origin": "http://127.0.0.1:5173",
        },
    )

    # Assert
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"