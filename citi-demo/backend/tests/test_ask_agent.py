"""Tests for the LangGraph vendor question API."""

import pytest
from fastapi.testclient import TestClient

from app.main import DATA_DIRECTORY, app
from app.semantic import get_contract_summaries

VENDOR_NAMES = [
    contract.vendor_name for contract in get_contract_summaries(DATA_DIRECTORY)
]


@pytest.mark.parametrize(
    ("question", "expected_route"),
    [
        ("Should we renew Aurelix Codeworks?", "renewal_review"),
        ("Should we renew Velmora Cloud Operations?", "renewal_review"),
        ("What is the budget and forecast?", "financial"),
        ("Which vendor is performing best?", "performance"),
        ("Which are the top perfoming vendors?", "performance"),
        ("Define reasoning of vendor score", "performance"),
        ("Compare Aurelix Codeworks and Velmora Cloud Operations quarterly performance.", "comparison"),
        ("Who are the competitors of Aurelix Codeworks?", "peers"),
        ("What should we negotiate with Aurelix Codeworks?", "negotiation"),
        ("What applications does Aurelix Codeworks support?", "dependency"),
    ],
)
def test_given_vendor_question_when_asked_then_routes_to_specialist(
    question: str, expected_route: str
) -> None:
    """The agent API returns an evidence-backed answer from the matching specialist."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.post("/api/ask", json={"question": question})

    # Assert
    assert response.status_code == 200
    answer = response.json()
    assert answer["route"] == expected_route
    assert answer["answer"]
    assert answer["evidence"]
    assert answer["source_files"]


def test_given_named_vendor_when_renewal_question_asked_then_returns_that_vendor_profile() -> None:
    """A non-priority vendor receives its own evidence rather than another vendor's queue."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.post(
        "/api/ask", json={"question": "Should we renew Velmora Cloud Operations?"}
    )

    # Assert
    assert response.status_code == 200
    assert "Velmora Cloud Operations" in response.json()["answer"]


@pytest.mark.parametrize("vendor_name", VENDOR_NAMES)
def test_given_each_source_vendor_when_renewal_question_asked_then_response_stays_vendor_scoped(
    vendor_name: str,
) -> None:
    """All 20 vendor renewal questions produce a scoped, evidence-backed response."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.post(
        "/api/ask", json={"question": f"Should we renew {vendor_name}?"}
    )

    # Assert
    assert response.status_code == 200
    answer = response.json()
    assert answer["route"] == "renewal_review"
    assert vendor_name in answer["answer"]
    assert answer["evidence"]


def test_given_performance_question_when_asked_then_returns_transparent_vendor_score() -> None:
    """The best-performing-vendor answer includes its explicit scoring evidence."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.post("/api/ask", json={"question": "Which vendor is performing best?"})

    # Assert
    assert response.status_code == 200
    answer = response.json()
    assert answer["route"] == "performance"
    assert "Elowyn Language Bureau" in answer["answer"]
    assert len(answer["evidence"]) == 5


def test_given_top_performing_vendor_question_when_asked_then_returns_ranked_vendors() -> None:
    """Common performance phrasing and misspellings return a transparent ranked list."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.post(
        "/api/ask", json={"question": "Which are the top perfoming vendors?"}
    )

    # Assert
    assert response.status_code == 200
    answer = response.json()
    assert answer["route"] == "performance"
    assert "Top-performing vendors" in answer["answer"]
    assert "Elowyn Language Bureau" in answer["answer"]
    assert len(answer["evidence"]) == 6


def test_given_top_performing_products_question_when_asked_then_returns_vendor_score_proxies() -> None:
    """Product questions disclose that available operational evidence is vendor-level only."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.post(
        "/api/ask", json={"question": "What are top performing products along with budget and forecast?"}
    )

    # Assert
    assert response.status_code == 200
    answer = response.json()
    assert answer["route"] == "performance"
    assert "no product-level performance measures" in answer["answer"]
    assert "PROD-" in answer["answer"]
    assert "Budget $" in answer["answer"]
    assert "Forecast $" in answer["answer"]
    assert any("Do not interpret this as a product-performance ranking" in item for item in answer["limitations"])


def test_given_two_named_vendors_when_comparison_asked_then_returns_commitment_and_period_evidence() -> None:
    """Vendor comparison answers distinguish commitments, financial periods, and SLA delivery proxy."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.post(
        "/api/ask",
        json={
            "question": "Compare Aurelix Codeworks and Velmora Cloud Operations monthly, quarterly, and delivery performance."
        },
    )

    # Assert
    assert response.status_code == 200
    answer = response.json()
    assert answer["route"] == "comparison"
    assert "Aurelix Codeworks" in answer["answer"]
    assert "Velmora Cloud Operations" in answer["answer"]
    assert len(answer["evidence"]) == 8
    assert any("Comparability:" in item for item in answer["evidence"])
    assert any("Reporting scope:" in item for item in answer["evidence"])


def test_given_named_vendor_when_negotiation_asked_then_returns_proposed_asks() -> None:
    """A negotiation question returns evidence-backed, non-binding commercial asks."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.post(
        "/api/ask",
        json={"question": "What should we negotiate with Aurelix Codeworks?"},
    )

    # Assert
    assert response.status_code == 200
    answer = response.json()
    assert answer["route"] == "negotiation"
    assert "Aurelix Codeworks" in answer["answer"]
    assert any("Proposed ask:" in item for item in answer["evidence"])
    assert any("signed pricing-adjustment clauses" in item for item in answer["limitations"])


def test_given_clarification_when_vendor_context_supplied_then_reuses_previous_specialist() -> None:
    """A clarification inherits the active vendor and the prior specialist route."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.post(
        "/api/ask",
        json={
            "question": "Why?",
            "context_vendor_name": "Aurelix Codeworks",
            "previous_route": "renewal_review",
        },
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["route"] == "renewal_review"
    assert "Aurelix Codeworks" in response.json()["answer"]


def test_given_comparison_follow_up_when_comparison_scope_supplied_then_retains_both_vendors() -> None:
    """A follow-up retains the complete prior comparison set without restating vendor names."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.post(
        "/api/ask",
        json={
            "question": "Which one is stronger overall?",
            "context_vendor_names": ["Aurelix Codeworks", "Velmora Cloud Operations"],
            "previous_route": "comparison",
        },
    )

    # Assert
    assert response.status_code == 200
    answer = response.json()
    assert answer["route"] == "comparison"
    assert "Aurelix Codeworks" in answer["answer"]
    assert "Velmora Cloud Operations" in answer["answer"]


def test_given_sla_status_follow_up_when_comparison_scope_supplied_then_returns_source_statuses() -> None:
    """An SLA-status follow-up uses the source status field for both compared vendors."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.post(
        "/api/ask",
        json={
            "question": "How did you derive the SLA status?",
            "context_vendor_names": ["Aurelix Codeworks", "Velmora Cloud Operations"],
            "previous_route": "comparison",
        },
    )

    # Assert
    assert response.status_code == 200
    answer = response.json()
    assert answer["route"] == "comparison"
    assert "interprets and validates" in answer["answer"]
    assert any("Aurelix Codeworks: definition - SLA_Status = At Risk" in item for item in answer["evidence"])
    assert any("Velmora Cloud Operations: definition - SLA_Status = Compliant" in item for item in answer["evidence"])
    assert any("measurement - Source_SLA_Actual_Percent" in item for item in answer["evidence"])
    assert any("validation - Source_SLA_Breach" in item for item in answer["evidence"])


def test_given_metric_follow_up_when_comparison_scope_supplied_then_explains_field_and_formula() -> None:
    """A named metric follow-up resolves source column, formula, and scoped source values."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.post(
        "/api/ask",
        json={
            "question": "How is YTD variance derived?",
            "context_vendor_names": ["Aurelix Codeworks", "Velmora Cloud Operations"],
            "previous_route": "comparison",
        },
    )

    # Assert
    assert response.status_code == 200
    answer = response.json()
    assert answer["route"] == "field_detail"
    assert "YTD_Variance_Percent" in answer["answer"]
    assert any("Actual YTD - Budget YTD" in item for item in answer["evidence"])
    assert any("Aurelix Codeworks: YTD_Variance_Percent = 2.00" in item for item in answer["evidence"])


def test_given_vendor_peer_question_when_asked_then_returns_category_aligned_candidates() -> None:
    """Peer discovery identifies source-aligned candidates without claiming direct interchangeability."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.post(
        "/api/ask", json={"question": "Who are the competitors of Aurelix Codeworks?"}
    )

    # Assert
    assert response.status_code == 200
    answer = response.json()
    assert answer["route"] == "peers"
    assert "Velmora Cloud Operations" in answer["answer"]
    assert any("Service_Category = Technology and Data" in item for item in answer["evidence"])
    assert any("Scope, volume, SLA definitions" in item for item in answer["limitations"])


def test_given_sla_status_field_follow_up_after_field_detail_then_returns_semantic_validation() -> None:
    """SLA_Status avoids a raw-field answer even when field detail was the preceding route."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.post(
        "/api/ask",
        json={
            "question": "How is SLA_Status calculated?",
            "context_vendor_names": ["Aurelix Codeworks", "Velmora Cloud Operations"],
            "previous_route": "field_detail",
        },
    )

    # Assert
    assert response.status_code == 200
    answer = response.json()
    assert answer["route"] == "field_detail"
    assert "interprets and validates" in answer["answer"]
    assert any("measurement - Source_SLA_Actual_Percent" in item for item in answer["evidence"])


def test_given_full_evidence_follow_up_when_comparison_scope_supplied_then_returns_calculation_trail() -> None:
    """Comparison evidence can be expanded into source lineage and calculation steps."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.post(
        "/api/ask",
        json={
            "question": "Explain all evidence values and calculations.",
            "context_vendor_names": ["Aurelix Codeworks", "Velmora Cloud Operations"],
            "previous_route": "comparison",
        },
    )

    # Assert
    assert response.status_code == 200
    answer = response.json()
    assert answer["route"] == "comparison"
    assert "Evidence calculation trail" in answer["answer"]
    assert any("Source_Annual_Base_Fee_USD" in item for item in answer["evidence"])
    assert any("(Actual YTD - Budget YTD) / Budget YTD x 100" in item for item in answer["evidence"])
    assert any("Jan_USD + Feb_USD + Mar_USD" in item for item in answer["evidence"])