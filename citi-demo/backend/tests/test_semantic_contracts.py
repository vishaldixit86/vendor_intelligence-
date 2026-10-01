"""Tests for canonical vendor-contract semantic records."""

from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app


def test_given_joined_sources_when_contracts_requested_then_returns_canonical_records() -> None:
    """Each forecast contract reports its linked financial and workforce coverage."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.get("/api/semantic/contracts")

    # Assert
    assert response.status_code == 200
    contracts = response.json()
    assert len(contracts) == 20
    assert all(contract["financial_record_count"] == 3 for contract in contracts)
    assert all(contract["renewal_decision_date"] for contract in contracts)
    assert all(contract["workforce_record_count"] == 3 for contract in contracts)
    assert all(contract["business_area"] for contract in contracts)
    assert all(contract["sla_status"] for contract in contracts)
    assert all(Decimal(contract["sla_target_percent"]) > 0 for contract in contracts)