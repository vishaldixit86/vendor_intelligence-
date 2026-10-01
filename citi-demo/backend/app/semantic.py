"""Semantic records derived from the Citi demo source datasets."""

import csv
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel


class ContractSummary(BaseModel):
    """Canonical vendor-contract record with linked source coverage."""

    annual_base_fee: Decimal
    application_count: int
    business_area: str
    contract_id: str
    financial_record_count: int
    renewal_decision_date: str
    risk_tier: str
    service_id: str
    sla_actual_percent: Decimal
    sla_status: str
    sla_target_percent: Decimal
    vendor_id: str
    vendor_name: str
    workforce_record_count: int


class FinancialScenarioTotal(BaseModel):
    """Total financial amount for one scenario and currency."""

    currency: str
    record_count: int
    scenario: str
    total_amount: Decimal


class OperationalContractProfile(BaseModel):
    """Operational risk and service profile for one vendor contract."""

    contract_id: str
    failure_impact: str
    renewal_decision_date: str
    risk_tier: str
    sla_status: str
    vendor_id: str
    vendor_name: str
    vrm_status: str
    workforce_dependency_risk: str


class VendorPerformanceAssessment(BaseModel):
    """Transparent performance score derived from vendor operational and financial fields."""

    score: int
    score_breakdown: list[str]
    vendor_name: str


class ProductPerformanceProxy(BaseModel):
    """Product identifier linked to its vendor's operational score, not a product score."""

    budget_amount: Decimal
    forecast_amount: Decimal
    product_id: str
    vendor_name: str
    vendor_operational_score: int


class VendorContractComparison(BaseModel):
    """Contract commitment and financial-period comparison for one vendor."""

    annual_base_fee: Decimal
    contract_id: str
    monthly_actual_ytd: Decimal
    monthly_budget_ytd: Decimal
    quarterly_actual_ytd: dict[str, Decimal]
    quarterly_budget_ytd: dict[str, Decimal]
    sla_actual_percent: Decimal
    sla_breached: bool
    sla_period: str
    sla_status: str
    sla_target_percent: Decimal
    vendor_name: str
    ytd_variance_percent: Decimal


class VendorComparisonEligibility(BaseModel):
    """Whether a vendor set supports category-specific or portfolio-level comparison."""

    actual_through: list[str]
    currencies: list[str]
    eligible_for_category_comparison: bool
    eligible_for_portfolio_comparison: bool
    reasons: list[str]
    service_categories: list[str]
    vendor_categories: list[str]


class SourceFieldExplanation(BaseModel):
    """Field-level lineage, values, and calculation guidance for a scoped follow-up."""

    definition: str
    derivation: str
    field_name: str
    source_file: str
    values: dict[str, str]


class VendorPeerCandidate(BaseModel):
    """Vendor candidate sharing the source-defined comparison category and reporting scope."""

    actual_through: str
    currency: str
    service_category: str
    vendor_name: str


class DecisionCandidate(BaseModel):
    """Draft decision candidate with the deterministic evidence that created it."""

    contract_id: str
    decision_id: str
    evidence: list[str]
    limitations: list[str]
    priority: str
    recommendation: str
    review_fields: list["ReviewField"]
    source_files: list[str]
    status: str
    vendor_name: str


class ReviewField(BaseModel):
    """A source-backed field that a reviewer must consider."""

    label: str
    source_file: str
    value: str


class DataQualityCheck(BaseModel):
    """Completeness result for one field in a source dataset."""

    field: str
    missing_record_count: int
    source_file: str
    total_record_count: int


class DataQualityReport(BaseModel):
    """Completeness evidence and warnings for semantic source fields."""

    checks: list[DataQualityCheck]
    warnings: list[str]


class GraphNode(BaseModel):
    """Entity node in the semantic relationship graph."""

    id: str
    label: str
    node_type: str


class GraphEdge(BaseModel):
    """Typed relationship edge in the semantic relationship graph."""

    id: str
    relation: str
    source: str
    target: str


class RelationshipGraph(BaseModel):
    """Graph of vendor, contract, service, and application relationships."""

    edges: list[GraphEdge]
    nodes: list[GraphNode]


def get_contract_summaries(data_directory: Path) -> list[ContractSummary]:
    """Build canonical vendor-contract records from the copied source CSV files."""
    financial_records = _read_csv(data_directory / "CT_Technology_Financials.csv")
    forecast_records = _read_csv(data_directory / "CT_Vendor_Technology_Forecast.csv")
    workforce_records = _read_csv(data_directory / "CT_Workforce_Organization.csv")

    financial_counts = Counter(_contract_key(record) for record in financial_records)
    workforce_counts = Counter(_contract_key(record) for record in workforce_records)
    applications_by_contract: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    for record in workforce_records:
        application = record.get("Application", "").strip()
        if application:
            applications_by_contract[_contract_key(record)].add(application)

    return [
        ContractSummary(
            annual_base_fee=Decimal(record.get("Source_Annual_Base_Fee_USD") or "0"),
            application_count=len(applications_by_contract[key]),
            business_area=" / ".join(
                value for value in (record.get("Entity", ""), record.get("OU", "")) if value
            ),
            contract_id=record["Contract_ID"],
            financial_record_count=financial_counts[key],
            renewal_decision_date=record.get("Renewal_Decision_Date", ""),
            risk_tier=record.get("Risk_Tier", "") or "Not assessed",
            service_id=record["Service_ID"],
            sla_actual_percent=Decimal(record.get("Source_SLA_Actual_Percent") or "0"),
            sla_status=record.get("SLA_Status", "") or "Not reported",
            sla_target_percent=Decimal(record.get("Source_SLA_Target_Percent") or "0"),
            vendor_id=record["Vendor_ID"],
            vendor_name=record["Vendor_Name"],
            workforce_record_count=workforce_counts[key],
        )
        for record in forecast_records
        if (key := _contract_key(record))
    ]


def get_data_quality_report(data_directory: Path) -> DataQualityReport:
    """Report completeness for all source fields used by semantic endpoints."""
    fields_by_source = {
        "CT_Technology_Financials.csv": [
            "Vendor_ID",
            "Contract_ID",
            "Scenario",
            "Currency",
            "Amount",
        ],
        "CT_Vendor_Technology_Forecast.csv": [
            "Vendor_ID",
            "Contract_ID",
            "Risk_Tier",
            "SLA_Status",
            "Renewal_Decision_Date",
            "VRM_Status",
        ],
        "CT_Workforce_Organization.csv": [
            "Vendor_ID",
            "Contract_ID",
            "Workforce_Dependency_Risk",
            "Failure_Impact",
        ],
    }
    checks: list[DataQualityCheck] = []

    for source_file, fields in fields_by_source.items():
        records = _read_csv(data_directory / source_file)
        for field in fields:
            missing_record_count = sum(
                1 for record in records if not record.get(field, "").strip()
            )
            checks.append(
                DataQualityCheck(
                    field=field,
                    missing_record_count=missing_record_count,
                    source_file=source_file,
                    total_record_count=len(records),
                )
            )

    warnings = [
        f"{check.source_file}: {check.field} is missing for "
        f"{check.missing_record_count} of {check.total_record_count} records."
        for check in checks
        if check.missing_record_count
    ]
    return DataQualityReport(checks=checks, warnings=warnings)


def get_renewal_review_candidates(data_directory: Path) -> list[DecisionCandidate]:
    """Create draft renewal-review candidates from the operational priority rule."""
    limitations = get_data_quality_report(data_directory).warnings
    candidates: list[DecisionCandidate] = []

    for profile in get_operational_contract_profiles(data_directory):
        has_high_contract_risk = profile.risk_tier == "High"
        has_high_workforce_dependency = profile.workforce_dependency_risk.startswith(
            "High"
        )
        if profile.sla_status != "At Risk" or not (
            has_high_contract_risk or has_high_workforce_dependency
        ):
            continue

        evidence = [f"SLA status: {profile.sla_status}."]
        if has_high_contract_risk:
            evidence.append(f"Contract risk tier: {profile.risk_tier}.")
        if has_high_workforce_dependency:
            evidence.append(
                f"Workforce dependency: {profile.workforce_dependency_risk}."
            )
        review_fields = [
            ReviewField(
                label="SLA status",
                source_file="CT_Vendor_Technology_Forecast.csv",
                value=profile.sla_status,
            ),
            ReviewField(
                label="Contract risk tier",
                source_file="CT_Vendor_Technology_Forecast.csv",
                value=profile.risk_tier or "Not provided",
            ),
            ReviewField(
                label="VRM status",
                source_file="CT_Vendor_Technology_Forecast.csv",
                value=profile.vrm_status or "Not provided",
            ),
            ReviewField(
                label="Renewal decision date",
                source_file="CT_Vendor_Technology_Forecast.csv",
                value=profile.renewal_decision_date or "Not provided",
            ),
            ReviewField(
                label="Workforce dependency",
                source_file="CT_Workforce_Organization.csv",
                value=profile.workforce_dependency_risk or "Not provided",
            ),
            ReviewField(
                label="Failure impact",
                source_file="CT_Workforce_Organization.csv",
                value=profile.failure_impact or "Not provided",
            ),
        ]
        candidates.append(
            DecisionCandidate(
                contract_id=profile.contract_id,
                decision_id=f"renewal-review:{profile.vendor_id}:{profile.contract_id}",
                evidence=evidence,
                limitations=limitations,
                priority="High",
                recommendation="Initiate a renewal and remediation review.",
                review_fields=review_fields,
                source_files=[
                    "CT_Vendor_Technology_Forecast.csv",
                    "CT_Workforce_Organization.csv",
                ],
                status="Draft",
                vendor_name=profile.vendor_name,
            )
        )
    return candidates


def get_relationship_graph(data_directory: Path) -> RelationshipGraph:
    """Build a deduplicated graph from contract and workforce source relationships."""
    forecast_records = _read_csv(data_directory / "CT_Vendor_Technology_Forecast.csv")
    workforce_records = _read_csv(data_directory / "CT_Workforce_Organization.csv")
    nodes: dict[str, GraphNode] = {}
    edges: dict[str, GraphEdge] = {}

    for record in forecast_records:
        vendor_node_id = f"vendor:{record['Vendor_ID']}"
        contract_node_id = f"contract:{record['Vendor_ID']}:{record['Contract_ID']}"
        service_node_id = f"service:{record['Service_ID']}"
        nodes[vendor_node_id] = GraphNode(
            id=vendor_node_id,
            label=record["Vendor_Name"],
            node_type="vendor",
        )
        nodes[contract_node_id] = GraphNode(
            id=contract_node_id,
            label=record["Contract_ID"],
            node_type="contract",
        )
        nodes[service_node_id] = GraphNode(
            id=service_node_id,
            label=record["Service_ID"],
            node_type="service",
        )
        _add_edge(edges, vendor_node_id, contract_node_id, "has_contract")
        _add_edge(edges, contract_node_id, service_node_id, "covers_service")

    for record in workforce_records:
        application = record.get("Application", "").strip()
        if not application:
            continue
        contract_node_id = f"contract:{record['Vendor_ID']}:{record['Contract_ID']}"
        application_node_id = f"application:{application}"
        nodes[application_node_id] = GraphNode(
            id=application_node_id,
            label=application,
            node_type="application",
        )
        _add_edge(edges, contract_node_id, application_node_id, "supports_application")

    return RelationshipGraph(
        edges=sorted(edges.values(), key=lambda edge: edge.id),
        nodes=sorted(nodes.values(), key=lambda node: node.id),
    )


def get_operational_contract_profiles(data_directory: Path) -> list[OperationalContractProfile]:
    """Return operational risk and SLA profile fields for each forecast contract."""
    forecast_records = _read_csv(data_directory / "CT_Vendor_Technology_Forecast.csv")
    workforce_records = _read_csv(data_directory / "CT_Workforce_Organization.csv")
    workforce_by_contract = {
        _contract_key(record): record
        for record in workforce_records
    }

    return [
        OperationalContractProfile(
            contract_id=record["Contract_ID"],
            failure_impact=workforce_record.get("Failure_Impact", ""),
            renewal_decision_date=record.get("Renewal_Decision_Date", ""),
            risk_tier=record.get("Risk_Tier", ""),
            sla_status=record.get("SLA_Status", ""),
            vendor_id=record["Vendor_ID"],
            vendor_name=record["Vendor_Name"],
            vrm_status=record.get("VRM_Status", ""),
            workforce_dependency_risk=workforce_record.get(
                "Workforce_Dependency_Risk", ""
            ),
        )
        for record in forecast_records
        if (workforce_record := workforce_by_contract.get(_contract_key(record)))
    ]


def get_vendor_performance_assessments(
    data_directory: Path,
) -> list[VendorPerformanceAssessment]:
    """Rank vendors using explicit SLA, risk, VRM, dependency, and budget-variance rules."""
    financial_records = _read_csv(data_directory / "CT_Technology_Financials.csv")
    actual_records_by_vendor = {
        record["Vendor_ID"]: record
        for record in financial_records
        if record.get("Scenario") == "Actual"
    }
    assessments: list[VendorPerformanceAssessment] = []

    for profile in get_operational_contract_profiles(data_directory):
        actual_record = actual_records_by_vendor.get(profile.vendor_id, {})
        budget_variance_percent = Decimal(
            actual_record.get("YTD_Variance_Percent") or "0"
        )
        sla_score = 40 if profile.sla_status == "Compliant" else 0
        risk_score = {"Low": 25, "Medium": 15, "High": 5}.get(profile.risk_tier, 0)
        vrm_score = 15 if profile.vrm_status == "Current" else 5
        dependency_score = (
            5
            if profile.workforce_dependency_risk.startswith("High")
            else 10
            if profile.workforce_dependency_risk.startswith("Medium")
            else 15
        )
        budget_score = 5 if budget_variance_percent <= 0 else 0
        score = sla_score + risk_score + vrm_score + dependency_score + budget_score
        assessments.append(
            VendorPerformanceAssessment(
                score=score,
                score_breakdown=[
                    f"SLA status {profile.sla_status}: {sla_score}/40.",
                    f"Contract risk tier {profile.risk_tier or 'not assessed'}: {risk_score}/25.",
                    f"VRM status {profile.vrm_status or 'not assessed'}: {vrm_score}/15.",
                    f"Workforce dependency {profile.workforce_dependency_risk}: {dependency_score}/15.",
                    f"Actual YTD variance versus budget {budget_variance_percent:+.2f}%: {budget_score}/5.",
                ],
                vendor_name=profile.vendor_name,
            )
        )
    return sorted(assessments, key=lambda assessment: (-assessment.score, assessment.vendor_name))


def get_product_performance_proxies(data_directory: Path) -> list[ProductPerformanceProxy]:
    """Link source product IDs to vendor operational scores without treating them as product metrics."""
    score_by_vendor = {
        assessment.vendor_name: assessment.score
        for assessment in get_vendor_performance_assessments(data_directory)
    }
    forecast_records = _read_csv(data_directory / "CT_Vendor_Technology_Forecast.csv")
    financial_by_vendor_product_and_scenario = {
        (record["Vendor_Name"], record["Product_ID"], record["Scenario"]): record
        for record in _read_csv(data_directory / "CT_Technology_Financials.csv")
    }
    return sorted(
        [
            ProductPerformanceProxy(
                budget_amount=Decimal(
                    financial_by_vendor_product_and_scenario.get(
                        (record["Vendor_Name"], record["Product_ID"], "Budget"), {}
                    ).get("Amount")
                    or "0"
                ),
                forecast_amount=Decimal(
                    financial_by_vendor_product_and_scenario.get(
                        (record["Vendor_Name"], record["Product_ID"], "Forecast"), {}
                    ).get("Amount")
                    or "0"
                ),
                product_id=record["Product_ID"],
                vendor_name=record["Vendor_Name"],
                vendor_operational_score=score_by_vendor[record["Vendor_Name"]],
            )
            for record in forecast_records
            if record.get("Product_ID") and record["Vendor_Name"] in score_by_vendor
        ],
        key=lambda proxy: (-proxy.vendor_operational_score, proxy.product_id),
    )


def get_vendor_contract_comparisons(
    data_directory: Path, vendor_names: list[str]
) -> list[VendorContractComparison]:
    """Compare named vendors against recorded commitments and monthly/quarterly financial data."""
    forecast_by_vendor = {
        record["Vendor_Name"]: record
        for record in _read_csv(data_directory / "CT_Vendor_Technology_Forecast.csv")
    }
    financial_records = _read_csv(data_directory / "CT_Technology_Financials.csv")
    comparisons: list[VendorContractComparison] = []

    for vendor_name in vendor_names:
        forecast_record = forecast_by_vendor.get(vendor_name)
        if forecast_record is None:
            continue
        actual_record = next(
            (
                record
                for record in financial_records
                if record["Vendor_Name"] == vendor_name and record["Scenario"] == "Actual"
            ),
            {},
        )
        budget_record = next(
            (
                record
                for record in financial_records
                if record["Vendor_Name"] == vendor_name and record["Scenario"] == "Budget"
            ),
            {},
        )
        comparisons.append(
            VendorContractComparison(
                annual_base_fee=Decimal(forecast_record["Source_Annual_Base_Fee_USD"]),
                contract_id=forecast_record["Contract_ID"],
                monthly_actual_ytd=Decimal(actual_record.get("YTD_Amount") or "0"),
                monthly_budget_ytd=Decimal(budget_record.get("Budget_YTD_Amount") or "0"),
                quarterly_actual_ytd=_quarterly_amounts(actual_record),
                quarterly_budget_ytd=_quarterly_amounts(budget_record),
                sla_actual_percent=Decimal(forecast_record["Source_SLA_Actual_Percent"]),
                sla_breached=forecast_record["Source_SLA_Breach"].lower() == "true",
                sla_period=forecast_record.get("Source_SLA_Period", "not recorded"),
                sla_status=forecast_record.get("SLA_Status", "not recorded"),
                sla_target_percent=Decimal(forecast_record["Source_SLA_Target_Percent"]),
                vendor_name=vendor_name,
                ytd_variance_percent=Decimal(actual_record.get("YTD_Variance_Percent") or "0"),
            )
        )
    return comparisons


def get_vendor_comparison_eligibility(
    data_directory: Path, vendor_names: list[str]
) -> VendorComparisonEligibility:
    """Assess source-defined scope, currency, and period compatibility before comparison."""
    actual_records = {
        record["Vendor_Name"]: record
        for record in _read_csv(data_directory / "CT_Technology_Financials.csv")
        if record.get("Scenario") == "Actual" and record["Vendor_Name"] in vendor_names
    }
    selected_records = [
        actual_records[vendor_name]
        for vendor_name in vendor_names
        if vendor_name in actual_records
    ]
    service_categories = sorted(
        {record.get("Service_Category", "not recorded") for record in selected_records}
    )
    vendor_categories = sorted(
        {record.get("Vendor_Category", "not recorded") for record in selected_records}
    )
    currencies = sorted({record.get("Currency", "not recorded") for record in selected_records})
    actual_through = sorted(
        {record.get("Actual_Through", "not recorded") for record in selected_records}
    )
    reasons: list[str] = []
    if len(selected_records) != len(vendor_names):
        reasons.append("Actual financial evidence is missing for one or more selected vendors.")
    if len(currencies) != 1:
        reasons.append("The selected vendors do not share a common reporting currency.")
    if len(actual_through) != 1:
        reasons.append("The selected vendors do not share an equivalent actual-through period.")
    if len(service_categories) != 1:
        reasons.append(
            "Service categories differ; do not rank raw SLA results as a like-for-like delivery comparison."
        )
    eligible_for_portfolio_comparison = (
        len(selected_records) == len(vendor_names) and len(currencies) == 1 and len(actual_through) == 1
    )
    return VendorComparisonEligibility(
        actual_through=actual_through,
        currencies=currencies,
        eligible_for_category_comparison=eligible_for_portfolio_comparison and len(service_categories) == 1,
        eligible_for_portfolio_comparison=eligible_for_portfolio_comparison,
        reasons=reasons or ["Comparable currency and reporting period; service category is aligned."],
        service_categories=service_categories,
        vendor_categories=vendor_categories,
    )


def get_vendor_peer_candidates(
    data_directory: Path, vendor_name: str | None = None
) -> tuple[str, list[VendorPeerCandidate]]:
    """Return source-aligned comparison candidates for a selected vendor or category pool."""
    actual_records = [
        record
        for record in _read_csv(data_directory / "CT_Technology_Financials.csv")
        if record.get("Scenario") == "Actual"
    ]
    selected_record = next(
        (record for record in actual_records if record["Vendor_Name"] == vendor_name),
        None,
    )
    service_category = selected_record.get("Service_Category", "") if selected_record else ""
    candidates = [
        VendorPeerCandidate(
            actual_through=record.get("Actual_Through", "not recorded"),
            currency=record.get("Currency", "not recorded"),
            service_category=record.get("Service_Category", "not recorded"),
            vendor_name=record["Vendor_Name"],
        )
        for record in actual_records
        if not service_category or record.get("Service_Category") == service_category
    ]
    return service_category, sorted(candidates, key=lambda candidate: candidate.vendor_name)


_FIELD_CATALOG = {
    "SLA_Status": {
        "aliases": ("sla status",),
        "definition": "Categorical service-performance state recorded by the source system for the SLA period.",
        "derivation": "Recorded source field. Validate it against Source_SLA_Actual_Percent, Source_SLA_Target_Percent, and Source_SLA_Breach; the source does not provide its complete classification policy.",
        "source_file": "CT_Vendor_Technology_Forecast.csv",
    },
    "Source_SLA_Actual_Percent": {
        "aliases": ("sla actual", "actual sla", "sla actual percent"),
        "definition": "Measured SLA percentage recorded for the source SLA period.",
        "derivation": "Recorded source measurement. The source does not provide the numerator or denominator required to independently recompute it.",
        "source_file": "CT_Vendor_Technology_Forecast.csv",
    },
    "Source_SLA_Target_Percent": {
        "aliases": ("sla target", "target sla", "sla target percent"),
        "definition": "Contractual SLA percentage target applicable to the recorded SLA period.",
        "derivation": "Recorded contractual target. The workbench compares actual minus target in percentage points.",
        "source_file": "CT_Vendor_Technology_Forecast.csv",
    },
    "Source_SLA_Breach": {
        "aliases": ("sla breach", "breach flag"),
        "definition": "Source boolean indicating whether an SLA breach was recorded for the source SLA period.",
        "derivation": "Recorded source flag; it is not recalculated by the workbench.",
        "source_file": "CT_Vendor_Technology_Forecast.csv",
    },
    "Source_Annual_Base_Fee_USD": {
        "aliases": ("annual base fee", "base fee", "annual commitment"),
        "definition": "Recorded annual base-fee commitment in USD for the vendor contract.",
        "derivation": "Recorded contract value; it is kept separate from actual invoices, budget, and forecast.",
        "source_file": "CT_Vendor_Technology_Forecast.csv",
    },
    "YTD_Amount": {
        "aliases": ("actual ytd", "ytd amount"),
        "definition": "Year-to-date financial amount for the selected scenario.",
        "derivation": "Recorded scenario amount. For performance comparison, the workbench uses the Actual scenario only.",
        "source_file": "CT_Technology_Financials.csv",
    },
    "Budget_YTD_Amount": {
        "aliases": ("budget ytd", "budget ytd amount"),
        "definition": "Budget baseline amount through the recorded actual-through date.",
        "derivation": "Recorded budget baseline; it is not combined with Actual or Forecast amounts.",
        "source_file": "CT_Technology_Financials.csv",
    },
    "YTD_Variance_Percent": {
        "aliases": ("ytd variance", "variance percent", "budget variance"),
        "definition": "Percentage difference between Actual YTD and Budget YTD for the recorded period.",
        "derivation": "(Actual YTD - Budget YTD) / Budget YTD x 100. A positive value is above budget; a negative value is below budget.",
        "source_file": "CT_Technology_Financials.csv",
    },
    "Service_Category": {
        "aliases": ("service category",),
        "definition": "Source category used to determine whether vendors can be compared on category-specific measures.",
        "derivation": "Recorded classification. The workbench requires matching service categories before ranking raw SLA performance.",
        "source_file": "CT_Technology_Financials.csv",
    },
    "Actual_Through": {
        "aliases": ("actual through", "reporting period"),
        "definition": "Last date through which Actual scenario data is recorded.",
        "derivation": "Recorded reporting cutoff. Comparisons require the same actual-through date across vendors.",
        "source_file": "CT_Technology_Financials.csv",
    },
}


def get_source_field_explanation(
    data_directory: Path, vendor_names: list[str], question: str
) -> SourceFieldExplanation | None:
    """Return cataloged source-field lineage and scoped values for a named follow-up field."""
    question_lower = question.lower()
    selected_field = next(
        (
            field_name
            for field_name, metadata in _FIELD_CATALOG.items()
            if field_name.lower() in question_lower
            or any(alias in question_lower for alias in metadata["aliases"])
        ),
        None,
    )
    if selected_field is None:
        return None
    metadata = _FIELD_CATALOG[selected_field]
    records = _read_csv(data_directory / metadata["source_file"])
    if metadata["source_file"] == "CT_Technology_Financials.csv":
        records = [record for record in records if record.get("Scenario") == "Actual"]
    values = {
        vendor_name: record.get(selected_field, "not recorded")
        for vendor_name in vendor_names
        if (record := next((item for item in records if item.get("Vendor_Name") == vendor_name), None))
    }
    return SourceFieldExplanation(
        definition=metadata["definition"],
        derivation=metadata["derivation"],
        field_name=selected_field,
        source_file=metadata["source_file"],
        values=values,
    )


def is_source_field_question(question: str) -> bool:
    """Return whether a question names a cataloged source field or user-facing alias."""
    question_lower = question.lower()
    return any(
        field_name.lower() in question_lower
        or any(alias in question_lower for alias in metadata["aliases"])
        for field_name, metadata in _FIELD_CATALOG.items()
    )


def get_financial_scenario_totals(
    data_directory: Path, vendor_id: str | None = None
) -> list[FinancialScenarioTotal]:
    """Return financial totals grouped by scenario and currency for an optional vendor."""
    financial_records = _read_csv(data_directory / "CT_Technology_Financials.csv")
    if vendor_id:
        financial_records = [
            record for record in financial_records if record["Vendor_ID"] == vendor_id
        ]
    totals: defaultdict[tuple[str, str], Decimal] = defaultdict(Decimal)
    record_counts: Counter[tuple[str, str]] = Counter()

    for record in financial_records:
        key = record["Scenario"], record["Currency"]
        totals[key] += Decimal(record["Amount"])
        record_counts[key] += 1

    return [
        FinancialScenarioTotal(
            currency=currency,
            record_count=record_counts[scenario, currency],
            scenario=scenario,
            total_amount=total_amount,
        )
        for (scenario, currency), total_amount in sorted(totals.items())
    ]


def _contract_key(record: dict[str, str]) -> tuple[str, str]:
    """Return the shared vendor-contract relationship key for a source record."""
    return record["Vendor_ID"], record["Contract_ID"]


def _quarterly_amounts(record: dict[str, str]) -> dict[str, Decimal]:
    """Aggregate monthly source amounts into calendar-quarter totals."""
    months_by_quarter = {
        "Q1": ("Jan_USD", "Feb_USD", "Mar_USD"),
        "Q2": ("Apr_USD", "May_USD", "Jun_USD"),
        "Q3": ("Jul_USD", "Aug_USD", "Sep_USD"),
        "Q4": ("Oct_USD", "Nov_USD", "Dec_USD"),
    }
    return {
        quarter: sum((Decimal(record.get(month) or "0") for month in months), Decimal())
        for quarter, months in months_by_quarter.items()
    }


def _add_edge(
    edges: dict[str, GraphEdge], source: str, target: str, relation: str
) -> None:
    """Add one graph edge, replacing any duplicate source-target-relation edge."""
    edge_id = f"{relation}:{source}:{target}"
    edges[edge_id] = GraphEdge(
        id=edge_id,
        relation=relation,
        source=source,
        target=target,
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV file as string-keyed records."""
    with path.open(encoding="utf-8", newline="") as source_file:
        return list(csv.DictReader(source_file))