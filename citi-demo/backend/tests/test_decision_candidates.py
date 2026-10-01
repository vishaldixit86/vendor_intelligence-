"""Tests for governed draft renewal-review decisions."""

from fastapi.testclient import TestClient

from app.main import app


def test_given_operational_priority_contracts_when_decisions_requested_then_returns_draft_evidence() -> None:
    """Priority contracts receive explainable draft renewal-review decisions."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.get("/api/decisions/renewal-reviews")

    # Assert
    assert response.status_code == 200
    candidates = response.json()
    assert len(candidates) == 4
    assert all(candidate["status"] == "Draft" for candidate in candidates)
    assert all(candidate["priority"] == "High" for candidate in candidates)
    assert all(candidate["evidence"] for candidate in candidates)
    assert all(len(candidate["source_files"]) == 2 for candidate in candidates)
    assert all(len(candidate["review_fields"]) == 6 for candidate in candidates)


def test_given_allow_list_source_when_requested_then_returns_csv() -> None:
    """Reviewers can inspect a cited source CSV from the API."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.get("/api/data/sources/CT_Vendor_Technology_Forecast.csv")

    # Assert
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")