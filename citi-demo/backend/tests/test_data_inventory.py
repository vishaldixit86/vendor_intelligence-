"""Tests for the source data inventory endpoint."""

from fastapi.testclient import TestClient

from app.main import app


def test_given_source_data_when_inventory_requested_then_returns_all_datasets() -> None:
    """The API reports the expected source files and their record counts."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.get("/api/data/inventory")

    # Assert
    assert response.status_code == 200
    assert [
        (dataset["name"], dataset["record_count"])
        for dataset in response.json()["datasets"]
    ] == [
        ("CT_Technology_Financials.csv", 60),
        ("CT_Vendor_Technology_Forecast.csv", 20),
        ("CT_Workforce_Organization.csv", 60),
    ]