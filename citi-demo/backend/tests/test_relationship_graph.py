"""Tests for the semantic relationship graph endpoint."""

from fastapi.testclient import TestClient

from app.main import app


def test_given_semantic_sources_when_graph_requested_then_returns_typed_relationships() -> None:
    """The graph exposes deduplicated entity nodes and their source relationships."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.get("/api/graph/relationships")

    # Assert
    assert response.status_code == 200
    graph = response.json()
    assert len(graph["nodes"]) == 64
    assert len(graph["edges"]) == 60
    assert {edge["relation"] for edge in graph["edges"]} == {
        "covers_service",
        "has_contract",
        "supports_application",
    }