"""Deterministic LangGraph workflow for explainable vendor questions."""

from pathlib import Path
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from app.semantic import (
    get_contract_summaries,
    get_data_quality_report,
    get_financial_scenario_totals,
    get_operational_contract_profiles,
    get_product_performance_proxies,
    get_relationship_graph,
    get_renewal_review_candidates,
    get_source_field_explanation,
    get_vendor_comparison_eligibility,
    get_vendor_contract_comparisons,
    get_vendor_peer_candidates,
    get_vendor_performance_assessments,
    is_source_field_question,
)


class AskResponse(BaseModel):
    """Evidence-backed response returned by the vendor question workflow."""

    answer: str
    evidence: list[str]
    limitations: list[str]
    route: Literal["comparison", "dependency", "field_detail", "financial", "negotiation", "peers", "performance", "renewal_review"]
    source_files: list[str]


class AgentState(TypedDict, total=False):
    """Shared state passed between the LangGraph router and specialist nodes."""

    answer: str
    context_vendor_name: str | None
    context_vendor_names: list[str]
    evidence: list[str]
    limitations: list[str]
    previous_route: Literal["comparison", "dependency", "field_detail", "financial", "negotiation", "peers", "performance", "renewal_review"] | None
    question: str
    route: Literal["comparison", "dependency", "field_detail", "financial", "negotiation", "peers", "performance", "renewal_review"]
    source_files: list[str]


def ask_question(
    question: str,
    data_directory: Path,
    *,
    context_vendor_name: str | None = None,
    context_vendor_names: list[str] | None = None,
    previous_route: Literal["comparison", "dependency", "field_detail", "financial", "negotiation", "peers", "performance", "renewal_review"] | None = None,
) -> AskResponse:
    """Route a vendor question through the LangGraph specialist workflow."""
    workflow = _build_workflow(data_directory)
    result = workflow.invoke(
        {
            "context_vendor_name": context_vendor_name,
            "context_vendor_names": context_vendor_names or [],
            "previous_route": previous_route,
            "question": question,
        }
    )
    return AskResponse(
        answer=result["answer"],
        evidence=result["evidence"],
        limitations=result["limitations"],
        route=result["route"],
        source_files=result["source_files"],
    )


def _build_workflow(data_directory: Path):
    """Create a routed LangGraph workflow bound to the demo source directory."""
    graph = StateGraph(AgentState)
    graph.add_node("route_question", _route_question)
    graph.add_node(
        "financial_specialist",
        lambda state: _answer_financial(state, data_directory=data_directory),
    )
    graph.add_node(
        "dependency_specialist",
        lambda state: _answer_dependency(state, data_directory=data_directory),
    )
    graph.add_node(
        "renewal_specialist",
        lambda state: _answer_renewal(state, data_directory=data_directory),
    )
    graph.add_node(
        "performance_specialist",
        lambda state: _answer_performance(state, data_directory=data_directory),
    )
    graph.add_node(
        "comparison_specialist",
        lambda state: _answer_comparison(state, data_directory=data_directory),
    )
    graph.add_node(
        "negotiation_specialist",
        lambda state: _answer_negotiation(state, data_directory=data_directory),
    )
    graph.add_node(
        "field_detail_specialist",
        lambda state: _answer_field_detail(state, data_directory=data_directory),
    )
    graph.add_node(
        "peer_specialist",
        lambda state: _answer_peers(state, data_directory=data_directory),
    )
    graph.add_edge(START, "route_question")
    graph.add_conditional_edges(
        "route_question",
        lambda state: state["route"],
        {
            "comparison": "comparison_specialist",
            "dependency": "dependency_specialist",
            "field_detail": "field_detail_specialist",
            "financial": "financial_specialist",
            "negotiation": "negotiation_specialist",
            "peers": "peer_specialist",
            "performance": "performance_specialist",
            "renewal_review": "renewal_specialist",
        },
    )
    graph.add_edge("financial_specialist", END)
    graph.add_edge("dependency_specialist", END)
    graph.add_edge("renewal_specialist", END)
    graph.add_edge("performance_specialist", END)
    graph.add_edge("comparison_specialist", END)
    graph.add_edge("negotiation_specialist", END)
    graph.add_edge("field_detail_specialist", END)
    graph.add_edge("peer_specialist", END)

    return graph.compile()


def _route_question(state: AgentState) -> AgentState:
    """Classify a question into one specialist route using transparent keywords."""
    question = state["question"].lower()
    if state.get("previous_route") == "comparison" and (
        _is_evidence_explanation(question) or "sla" in question
    ):
        route: Literal["comparison", "dependency", "field_detail", "financial", "negotiation", "performance", "renewal_review"] = "comparison"
    elif state.get("previous_route") and is_source_field_question(question):
        route: Literal["comparison", "dependency", "field_detail", "financial", "negotiation", "performance", "renewal_review"] = "field_detail"
    elif any(word in question for word in ("negotiate", "negotiation", "concession", "commercial terms")):
        route = "negotiation"
    elif any(phrase in question for phrase in ("competitor", "competitors", "peer vendor", "peer vendors", "comparable vendor", "similar vendor")):
        route = "peers"
    elif any(word in question for word in ("compare", "commitment", "quarterly", "monthly", "on time", "deliver")):
        route = "comparison"
    elif any(
        word in question
        for word in (
            "best",
            "performing",
            "perfoming",
            "performance",
            "vendor score",
            "operational score",
            "top vendor",
            "top vendors",
        )
    ):
        route = "performance"
    elif any(word in question for word in ("renew", "renegotiate", "risk", "sla", "review")):
        route: Literal["dependency", "financial", "renewal_review"] = "renewal_review"
    elif any(word in question for word in ("budget", "cost", "forecast", "actual", "spend")):
        route = "financial"
    elif state.get("previous_route") and _is_follow_up(question):
        route = state["previous_route"]
    else:
        route = "dependency"
    return {"route": route}


def _answer_performance(state: AgentState, *, data_directory: Path) -> AgentState:
    """Rank vendor operational performance using explicit source-backed score components."""
    assessments = get_vendor_performance_assessments(data_directory)
    top_assessment = assessments[0]
    question = state["question"].lower()
    if "product" in question:
        proxies = get_product_performance_proxies(data_directory)[:5]
        return {
            "answer": "The source has Product_ID links but no product-level performance measures. These are the products associated with the highest-scoring vendors, not a product-performance ranking: "
            + "; ".join(
                f"{proxy.product_id} ({proxy.vendor_name}, vendor score {proxy.vendor_operational_score}/100, Budget ${proxy.budget_amount:,.2f}, Forecast ${proxy.forecast_amount:,.2f})"
                for proxy in proxies
            )
            + ".",
            "evidence": [
                "Product_ID is recorded in CT_Vendor_Technology_Forecast.csv and links a product to a vendor contract.",
                "The displayed score is the vendor operational score, based on SLA status, contract risk tier, VRM status, workforce dependency, and Actual YTD variance. Budget and Forecast are separate financial scenarios linked by Product_ID.",
                *[
                    f"{proxy.product_id}: linked vendor {proxy.vendor_name}; vendor operational score {proxy.vendor_operational_score}/100; Budget ${proxy.budget_amount:,.2f}; Forecast ${proxy.forecast_amount:,.2f}."
                    for proxy in proxies
                ],
            ],
            "limitations": [
                *get_data_quality_report(data_directory).warnings,
                "No product-level SLA, incidents, service volume, adoption, cost allocation, or outcome measure is supplied. Do not interpret this as a product-performance ranking.",
            ],
            "source_files": [
                "CT_Vendor_Technology_Forecast.csv",
                "CT_Workforce_Organization.csv",
                "CT_Technology_Financials.csv",
            ],
        }
    if "top" in question:
        ranked_vendors = assessments[:5]
        return {
            "answer": "Top-performing vendors under the transparent operational score: "
            + "; ".join(
                f"{assessment.vendor_name} ({assessment.score}/100)"
                for assessment in ranked_vendors
            )
            + ".",
            "evidence": [
                "Score components: SLA status 40 points; contract risk tier 25; VRM status 15; workforce dependency 15; Actual YTD variance versus budget 5.",
                *[
                    f"{assessment.vendor_name}: {assessment.score}/100."
                    for assessment in ranked_vendors
                ],
            ],
            "limitations": [
                *get_data_quality_report(data_directory).warnings,
                "This is an operational score, not a final procurement decision, a service-value measure, or a like-for-like category comparison.",
            ],
            "source_files": [
                "CT_Vendor_Technology_Forecast.csv",
                "CT_Workforce_Organization.csv",
                "CT_Technology_Financials.csv",
            ],
        }
    return {
        "answer": f"{top_assessment.vendor_name} is currently the best-performing vendor under the transparent operational score, with {top_assessment.score}/100.",
        "evidence": top_assessment.score_breakdown,
        "limitations": [
            *get_data_quality_report(data_directory).warnings,
            "This is an operational score, not a final procurement decision or a measure of service value.",
        ],
        "source_files": [
            "CT_Vendor_Technology_Forecast.csv",
            "CT_Workforce_Organization.csv",
            "CT_Technology_Financials.csv",
        ],
    }


def _answer_peers(state: AgentState, *, data_directory: Path) -> AgentState:
    """Identify category and reporting-scope aligned peer candidates without claiming interchangeability."""
    question = _question_with_context(state)
    profile = _find_operational_profile(question, data_directory)
    service_category, candidates = get_vendor_peer_candidates(
        data_directory, profile.vendor_name if profile else None
    )
    if not candidates:
        return {
            "answer": "Name a vendor to identify source-aligned peer candidates.",
            "evidence": [],
            "limitations": get_data_quality_report(data_directory).warnings,
            "source_files": ["CT_Technology_Financials.csv"],
        }
    candidate_names = [candidate.vendor_name for candidate in candidates]
    if profile:
        candidate_names = [name for name in candidate_names if name != profile.vendor_name]
    subject = f" for {profile.vendor_name}" if profile else ""
    return {
        "answer": f"Source-aligned peer candidates{subject}: {', '.join(candidate_names)}.",
        "evidence": [
            f"Peer screen: Service_Category = {service_category or 'all source categories'}.",
            *[
                f"{candidate.vendor_name}: {candidate.service_category}; {candidate.currency}; Actual_Through {candidate.actual_through}."
                for candidate in candidates
                if not profile or candidate.vendor_name != profile.vendor_name
            ],
        ],
        "limitations": [
            *get_data_quality_report(data_directory).warnings,
            "Peer candidates share the recorded service category. Scope, volume, SLA definitions, transition readiness, and commercial model still require validation before a competitive sourcing or replacement decision.",
        ],
        "source_files": ["CT_Technology_Financials.csv"],
    }


def _answer_field_detail(state: AgentState, *, data_directory: Path) -> AgentState:
    """Explain a named source field using its cataloged definition, formula, and scoped values."""
    question = _question_with_context(state)
    vendor_names = [
        contract.vendor_name
        for contract in get_contract_summaries(data_directory)
        if contract.vendor_name.lower() in question.lower()
    ]
    explanation = get_source_field_explanation(data_directory, vendor_names, question)
    if explanation is None:
        return {
            "answer": "Name a source field or metric from the prior response to inspect its definition, lineage, and calculation.",
            "evidence": [],
            "limitations": get_data_quality_report(data_directory).warnings,
            "source_files": [],
        }
    if explanation.field_name == "SLA_Status":
        comparisons = get_vendor_contract_comparisons(data_directory, vendor_names)
        return _answer_sla_status_detail(comparisons, data_directory)
    return {
        "answer": f"{explanation.field_name}: {explanation.definition}",
        "evidence": [
            f"Source column: {explanation.source_file}.{explanation.field_name}.",
            f"Derivation: {explanation.derivation}",
            *[f"{vendor_name}: {explanation.field_name} = {value}." for vendor_name, value in explanation.values.items()],
        ],
        "limitations": [
            *get_data_quality_report(data_directory).warnings,
            "Values are limited to the active vendor or comparison scope and the source reporting period.",
        ],
        "source_files": [explanation.source_file],
    }


def _answer_comparison(state: AgentState, *, data_directory: Path) -> AgentState:
    """Compare named vendors using contractual, financial-period, and SLA evidence."""
    question = _question_with_context(state)
    vendor_names = [
        contract.vendor_name
        for contract in get_contract_summaries(data_directory)
        if contract.vendor_name.lower() in question.lower()
    ]
    comparisons = get_vendor_contract_comparisons(data_directory, vendor_names)
    if len(comparisons) < 2:
        return {
            "answer": "Name two vendors to compare their contractual commitments, monthly and quarterly financial performance, and SLA delivery proxy.",
            "evidence": [],
            "limitations": get_data_quality_report(data_directory).warnings,
            "source_files": [
                "CT_Vendor_Technology_Forecast.csv",
                "CT_Technology_Financials.csv",
            ],
        }

    eligibility = get_vendor_comparison_eligibility(data_directory, vendor_names)
    if _is_evidence_explanation(question):
        return _answer_comparison_evidence_detail(comparisons, eligibility, data_directory)
    if "sla" in question.lower():
        return _answer_sla_status_detail(comparisons, data_directory)
    evidence = [
        "Comparability: "
        + (
            "category-specific comparison is supported."
            if eligibility.eligible_for_category_comparison
            else "portfolio-level commercial comparison only; category-specific SLA ranking is not supported."
        ),
        f"Reporting scope: currency {', '.join(eligibility.currencies)}; actuals through {', '.join(eligibility.actual_through)}; service categories {', '.join(eligibility.service_categories)}.",
    ]
    for comparison in comparisons:
        delivery_status = "breached" if comparison.sla_breached else "met"
        evidence.extend(
            [
                f"{comparison.vendor_name}: annual base-fee commitment ${comparison.annual_base_fee:,.2f}; SLA {comparison.sla_actual_percent:.4f}% versus {comparison.sla_target_percent:.2f}% target ({delivery_status}).",
                f"{comparison.vendor_name}: Actual YTD ${comparison.monthly_actual_ytd:,.2f} versus budget YTD ${comparison.monthly_budget_ytd:,.2f} ({comparison.ytd_variance_percent:+.2f}%).",
                f"{comparison.vendor_name}: Q1 actual ${comparison.quarterly_actual_ytd['Q1']:,.2f} versus budget ${comparison.quarterly_budget_ytd['Q1']:,.2f}; Q2 actual ${comparison.quarterly_actual_ytd['Q2']:,.2f} versus budget ${comparison.quarterly_budget_ytd['Q2']:,.2f}.",
            ]
        )
    return {
        "answer": f"Compared {', '.join(comparison.vendor_name for comparison in comparisons)} against their recorded contract commitments and financial performance. SLA delivery status is used as the available on-time delivery proxy.",
        "evidence": evidence,
        "limitations": [
            *get_data_quality_report(data_directory).warnings,
            *eligibility.reasons,
            "The source data does not include milestone delivery dates; SLA breach status is the on-time delivery proxy.",
        ],
        "source_files": [
            "CT_Vendor_Technology_Forecast.csv",
            "CT_Technology_Financials.csv",
        ],
    }


def _answer_sla_status_detail(comparisons: list, data_directory: Path) -> AgentState:
    """Explain and validate source SLA status with the related measurements and breach flag."""
    return {
        "answer": "SLA_Status is the source system's categorical assessment for the recorded SLA period. The workbench interprets and validates it using the recorded actual versus target gap and breach flag: below target or a recorded breach is operationally at risk; at or above target without a breach is compliant. This validates the label but does not replace the source system's own classification rule.",
        "evidence": [
            evidence_item
            for comparison in comparisons
            for evidence_item in (
                f"{comparison.vendor_name}: definition - SLA_Status = {comparison.sla_status}, the source assessment for Source_SLA_Period {comparison.sla_period}.",
                f"{comparison.vendor_name}: measurement - Source_SLA_Actual_Percent {comparison.sla_actual_percent:.4f}% minus Source_SLA_Target_Percent {comparison.sla_target_percent:.2f}% = {comparison.sla_actual_percent - comparison.sla_target_percent:+.4f} percentage points.",
                f"{comparison.vendor_name}: validation - Source_SLA_Breach = {str(comparison.sla_breached).lower()}; the source status is {'consistent' if (comparison.sla_breached or comparison.sla_actual_percent < comparison.sla_target_percent) == (comparison.sla_status.lower() == 'at risk') else 'not fully explained by the available fields'} with the transparent validation rule.",
            )
        ],
        "limitations": [
            *get_data_quality_report(data_directory).warnings,
            "The CSV does not document the source system's full SLA_Status classification policy, SLA numerator and denominator, incident history, or delivery milestones. The validation rule is an explainable interpretation, not a replacement for that missing policy.",
        ],
        "source_files": ["CT_Vendor_Technology_Forecast.csv"],
    }


def _answer_comparison_evidence_detail(
    comparisons: list, eligibility, data_directory: Path
) -> AgentState:
    """Explain source lineage and deterministic calculations behind a vendor comparison."""
    evidence = [
        "Comparison eligibility: Service_Category, Currency, and Actual_Through are recorded fields. Matching service category, currency, and actual-through period allow category-specific comparison."
    ]
    for comparison in comparisons:
        evidence.extend(
            [
                f"{comparison.vendor_name} annual base-fee commitment ${comparison.annual_base_fee:,.2f}: recorded in CT_Vendor_Technology_Forecast.csv.Source_Annual_Base_Fee_USD; it is not calculated from spend.",
                f"{comparison.vendor_name} SLA actual {comparison.sla_actual_percent:.4f}% and target {comparison.sla_target_percent:.2f}%: recorded in Source_SLA_Actual_Percent and Source_SLA_Target_Percent. Gap = actual minus target = {comparison.sla_actual_percent - comparison.sla_target_percent:+.4f} percentage points; breach is the recorded Source_SLA_Breach flag.",
                f"{comparison.vendor_name} Actual YTD ${comparison.monthly_actual_ytd:,.2f}: recorded in the Actual scenario YTD_Amount. Budget YTD ${comparison.monthly_budget_ytd:,.2f}: recorded in the Budget scenario Budget_YTD_Amount; scenarios remain separate.",
                f"{comparison.vendor_name} YTD variance {comparison.ytd_variance_percent:+.2f}%: source field YTD_Variance_Percent, validated as (Actual YTD - Budget YTD) / Budget YTD x 100.",
                f"{comparison.vendor_name} quarterly values: Q1 is Jan_USD + Feb_USD + Mar_USD; Q2 is Apr_USD + May_USD + Jun_USD, calculated separately for Actual and Budget source records.",
            ]
        )
    return {
        "answer": "Evidence calculation trail for the active vendor comparison. Each item identifies whether it is recorded directly in a CSV field or calculated deterministically from named source fields.",
        "evidence": evidence,
        "limitations": [
            *get_data_quality_report(data_directory).warnings,
            *eligibility.reasons,
            "SLA delivery status is not evidence of milestone delivery timeliness because the source has no delivery-milestone dates.",
        ],
        "source_files": [
            "CT_Vendor_Technology_Forecast.csv",
            "CT_Technology_Financials.csv",
        ],
    }


def _answer_negotiation(state: AgentState, *, data_directory: Path) -> AgentState:
    """Prepare a negotiation brief from vendor-specific contractual and performance evidence."""
    question = _question_with_context(state)
    profile = _find_operational_profile(question, data_directory)
    if profile is None:
        return {
            "answer": "Name a vendor to prepare a negotiation brief from its contract, SLA, and financial evidence.",
            "evidence": [],
            "limitations": get_data_quality_report(data_directory).warnings,
            "source_files": [
                "CT_Vendor_Technology_Forecast.csv",
                "CT_Technology_Financials.csv",
                "CT_Workforce_Organization.csv",
            ],
        }

    comparison = get_vendor_contract_comparisons(data_directory, [profile.vendor_name])[0]
    proposed_asks = [
        f"Seek a price hold or offset against the ${comparison.annual_base_fee:,.2f} annual base-fee commitment.",
        "Require a time-bound SLA remediation plan with measurable recovery checkpoints."
        if comparison.sla_breached
        else "Preserve the current SLA target and add measurable service-review checkpoints.",
        "Set a quarterly financial review against the agreed budget baseline."
        if comparison.ytd_variance_percent > 0
        else "Use the favorable YTD position as a baseline for renewal price discipline.",
    ]
    return {
        "answer": f"Negotiation brief for {profile.vendor_name}: use the recorded contract and performance evidence to seek commercial protection and service commitments. These are proposed asks, not approved contract terms.",
        "evidence": [
            f"Annual base-fee commitment: ${comparison.annual_base_fee:,.2f}.",
            f"SLA: {comparison.sla_actual_percent:.4f}% actual versus {comparison.sla_target_percent:.2f}% target ({'breached' if comparison.sla_breached else 'met'}).",
            f"Actual YTD: ${comparison.monthly_actual_ytd:,.2f} versus budget YTD ${comparison.monthly_budget_ytd:,.2f} ({comparison.ytd_variance_percent:+.2f}%).",
            f"Operational dependency: {profile.workforce_dependency_risk}.",
            *[f"Proposed ask: {ask}" for ask in proposed_asks],
        ],
        "limitations": [
            *get_data_quality_report(data_directory).warnings,
            "The CSVs do not provide signed pricing-adjustment clauses, service credits, termination rights, or milestone delivery dates; validate those terms in the executed contract before negotiation.",
        ],
        "source_files": [
            "CT_Vendor_Technology_Forecast.csv",
            "CT_Technology_Financials.csv",
            "CT_Workforce_Organization.csv",
        ],
    }


def _answer_financial(state: AgentState, *, data_directory: Path) -> AgentState:
    """Answer financial scenario questions without combining scenarios."""
    profile = _find_operational_profile(
        _question_with_context(state), data_directory
    )
    totals = get_financial_scenario_totals(
        data_directory, profile.vendor_id if profile else None
    )
    subject = f" for {profile.vendor_name}" if profile else ""
    answer = f"Financial scenarios remain separate{subject}: " + "; ".join(
        f"{total.scenario} ${total.total_amount:,.2f}" for total in totals
    ) + "."
    return {
        "answer": answer,
        "evidence": [
            f"{total.scenario}: {total.record_count} {total.currency} source records."
            for total in totals
        ],
        "limitations": get_data_quality_report(data_directory).warnings,
        "source_files": ["CT_Technology_Financials.csv"],
    }


def _answer_dependency(state: AgentState, *, data_directory: Path) -> AgentState:
    """Answer relationship questions from the canonical semantic graph."""
    graph = get_relationship_graph(data_directory)
    matched_node = _find_node(_question_with_context(state), graph.nodes)
    if matched_node is None:
        return {
            "answer": "The graph contains 20 vendors, 20 contracts, 20 services, and 4 applications. Name a vendor, contract, service, or application to trace its direct relationships.",
            "evidence": [f"{len(graph.nodes)} graph entities and {len(graph.edges)} typed relationships are available."],
            "limitations": get_data_quality_report(data_directory).warnings,
            "source_files": [
                "CT_Vendor_Technology_Forecast.csv",
                "CT_Workforce_Organization.csv",
            ],
        }

    connected_edges = [
        edge for edge in graph.edges if edge.source == matched_node.id or edge.target == matched_node.id
    ]
    node_by_id = {node.id: node for node in graph.nodes}
    relationships = [
        f"{edge.relation.replace('_', ' ')} {node_by_id[edge.target if edge.source == matched_node.id else edge.source].label}"
        for edge in connected_edges
    ]
    return {
        "answer": f"{matched_node.label} has {len(relationships)} direct relationship(s): " + "; ".join(relationships) + ".",
        "evidence": [f"Graph node type: {matched_node.node_type}.", *relationships],
        "limitations": get_data_quality_report(data_directory).warnings,
        "source_files": [
            "CT_Vendor_Technology_Forecast.csv",
            "CT_Workforce_Organization.csv",
        ],
    }


def _answer_renewal(state: AgentState, *, data_directory: Path) -> AgentState:
    """Answer renewal and risk questions from governed draft decision candidates."""
    candidates = get_renewal_review_candidates(data_directory)
    question_with_context = _question_with_context(state)
    profile = _find_operational_profile(question_with_context, data_directory)
    selected_candidates = _matching_candidates(question_with_context, candidates)
    if profile and not selected_candidates:
        return {
            "answer": f"{profile.vendor_name} does not currently meet the high-priority human-review rule. Its profile shows SLA status {profile.sla_status}, risk tier {profile.risk_tier or 'not assessed'}, and workforce dependency {profile.workforce_dependency_risk}. Final decisions require authorized human review.",
            "evidence": [
                f"SLA status: {profile.sla_status}.",
                f"Contract risk tier: {profile.risk_tier or 'not assessed'}.",
                f"Workforce dependency: {profile.workforce_dependency_risk}.",
            ],
            "limitations": get_data_quality_report(data_directory).warnings,
            "source_files": [
                "CT_Vendor_Technology_Forecast.csv",
                "CT_Workforce_Organization.csv",
            ],
        }

    selected_candidates = selected_candidates or candidates
    selected_names = ", ".join(candidate.vendor_name for candidate in selected_candidates)
    evidence = [item for candidate in selected_candidates for item in candidate.evidence]
    return {
        "answer": f"Proposed action: initiate a renewal and remediation review for {selected_names}. This is not approved until authorized human review is complete.",
        "evidence": evidence,
        "limitations": get_data_quality_report(data_directory).warnings,
        "source_files": [
            "CT_Vendor_Technology_Forecast.csv",
            "CT_Workforce_Organization.csv",
        ],
    }


def _find_node(question: str, nodes: list) -> object | None:
    """Return the first graph node whose label appears in a question."""
    question_lower = question.lower()
    return next((node for node in nodes if node.label.lower() in question_lower), None)


def _matching_candidates(question: str, candidates: list) -> list:
    """Return draft decisions whose vendor name appears in a question."""
    question_lower = question.lower()
    return [candidate for candidate in candidates if candidate.vendor_name.lower() in question_lower]


def _find_operational_profile(question: str, data_directory: Path):
    """Return the operational profile for the vendor explicitly named in a question."""
    question_lower = question.lower()
    return next(
        (
            profile
            for profile in get_operational_contract_profiles(data_directory)
            if profile.vendor_name.lower() in question_lower
        ),
        None,
    )


def _is_follow_up(question: str) -> bool:
    """Return whether a question should inherit the preceding bounded analysis scope."""
    normalized_question = question.strip()
    if normalized_question in {
        "why",
        "why?",
        "explain",
        "explain more",
        "more detail",
        "tell me more",
    }:
        return True
    return normalized_question.startswith((
        "and ",
        "what about ",
        "which one ",
        "how about ",
        "how is ",
        "how are ",
        "can you ",
        "explain ",
    ))


def _is_evidence_explanation(question: str) -> bool:
    """Return whether a question requests the full evidence and calculation trail."""
    return any(
        phrase in question
        for phrase in (
            "explain all evidence",
            "explain the evidence",
            "all evidence values",
            "all values",
            "calculation trail",
            "how are all",
        )
    )


def _question_with_context(state: AgentState) -> str:
    """Append the active vendor or comparison set when the question omits it."""
    question = state["question"]
    context_vendor_names = state.get("context_vendor_names") or []
    if not context_vendor_names and state.get("context_vendor_name"):
        context_vendor_names = [state["context_vendor_name"]]
    missing_vendor_names = [
        vendor_name
        for vendor_name in context_vendor_names
        if vendor_name.lower() not in question.lower()
    ]
    return f"{question} {' '.join(missing_vendor_names)}" if missing_vendor_names else question