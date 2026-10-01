"""Tests for scenario-safe financial semantic summaries."""

from fastapi.testclient import TestClient

from app.main import app


def test_given_financial_scenarios_when_summary_requested_then_totals_remain_separate() -> None:
    """Actual, Budget, and Forecast totals are presented as independent scenarios."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.get("/api/semantic/financials/summary")

    # Assert
    assert response.status_code == 200
    summaries = response.json()
    assert [summary["scenario"] for summary in summaries] == [
        "Actual",
        "Budget",
        "Forecast",
    ]
    assert all(summary["currency"] == "USD" for summary in summaries)
    assert all(summary["record_count"] == 20 for summary in summaries)