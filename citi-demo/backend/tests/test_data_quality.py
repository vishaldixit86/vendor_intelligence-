"""Tests for the source data quality endpoint."""

from fastapi.testclient import TestClient

from app.main import app


def test_given_semantic_sources_when_quality_requested_then_returns_completeness_evidence() -> None:
    """The API surfaces the known missing risk tier as a warning."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.get("/api/data/quality")

    # Assert
    assert response.status_code == 200
    report = response.json()
    assert len(report["checks"]) == 15
    assert report["warnings"] == [
        "CT_Vendor_Technology_Forecast.csv: Risk_Tier is missing for 1 of 20 records."
    ]