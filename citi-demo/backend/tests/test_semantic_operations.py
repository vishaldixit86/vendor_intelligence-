"""Tests for the operational contract semantic view."""

from fastapi.testclient import TestClient

from app.main import app


def test_given_joined_operational_sources_when_profiles_requested_then_returns_contract_profiles() -> None:
    """Each contract exposes its SLA and workforce dependency risk profile."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.get("/api/semantic/operations/contracts")

    # Assert
    assert response.status_code == 200
    profiles = response.json()
    assert len(profiles) == 20
    assert {profile["sla_status"] for profile in profiles} == {"At Risk", "Compliant"}
    assert all(profile["workforce_dependency_risk"] for profile in profiles)