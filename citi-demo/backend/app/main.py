"""FastAPI entry point for the Citi vendor decision intelligence demo."""

import csv
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.agents.workflow import AskResponse, ask_question
from app.semantic import (
    ContractSummary,
    DataQualityReport,
    DecisionCandidate,
    FinancialScenarioTotal,
    OperationalContractProfile,
    RelationshipGraph,
    get_contract_summaries,
    get_data_quality_report,
    get_financial_scenario_totals,
    get_operational_contract_profiles,
    get_relationship_graph,
    get_renewal_review_candidates,
)

DATA_DIRECTORY = Path(__file__).resolve().parents[2] / "data"
SOURCE_FILES = frozenset(
    {
        "CT_Technology_Financials.csv",
        "CT_Vendor_Technology_Forecast.csv",
        "CT_Workforce_Organization.csv",
    }
)


class HealthResponse(BaseModel):
    """Health response returned by the API."""

    status: str
    service: str


class AskRequest(BaseModel):
    """Question submitted to the vendor decision workflow."""

    question: str = Field(min_length=3, max_length=500)
    context_vendor_name: str | None = Field(default=None, max_length=200)
    context_vendor_names: list[str] = Field(default_factory=list, max_length=20)
    previous_route: str | None = Field(default=None, max_length=50)


class DatasetSummary(BaseModel):
    """Metadata for one source dataset."""

    columns: list[str]
    name: str
    record_count: int


class DataInventoryResponse(BaseModel):
    """Read-only overview of data available to the API."""

    datasets: list[DatasetSummary]


def get_data_inventory() -> DataInventoryResponse:
    """Return schema metadata and record counts for the demo CSV sources."""
    datasets: list[DatasetSummary] = []
    for dataset_path in sorted(DATA_DIRECTORY.glob("*.csv")):
        with dataset_path.open(encoding="utf-8", newline="") as dataset_file:
            reader = csv.reader(dataset_file)
            columns = next(reader, [])
            record_count = sum(1 for _ in reader)
        datasets.append(
            DatasetSummary(
                columns=columns,
                name=dataset_path.name,
                record_count=record_count,
            )
        )
    return DataInventoryResponse(datasets=datasets)


def create_app() -> FastAPI:
    """Create and configure the Citi demo API."""
    app = FastAPI(
        title="Citi Vendor Decision Intelligence API",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", response_model=HealthResponse, tags=["system"])
    def get_health() -> HealthResponse:
        """Return the API health state."""
        return HealthResponse(status="ok", service="vendor-decision-intelligence")

    @app.post("/api/ask", response_model=AskResponse, tags=["agents"])
    def ask_vendor_question(request: AskRequest) -> AskResponse:
        """Route a vendor question through the LangGraph specialist workflow."""
        return ask_question(
            request.question,
            DATA_DIRECTORY,
            context_vendor_name=request.context_vendor_name,
            context_vendor_names=request.context_vendor_names,
            previous_route=request.previous_route,
        )

    @app.get("/api/data/inventory", response_model=DataInventoryResponse, tags=["data"])
    def get_inventory() -> DataInventoryResponse:
        """List the source data that is available to the API."""
        return get_data_inventory()

    @app.get("/api/data/sources/{source_file}", tags=["data"])
    def get_source_file(source_file: str) -> FileResponse:
        """Return one allow-listed CSV source for reviewer inspection."""
        if source_file not in SOURCE_FILES:
            raise HTTPException(status_code=404, detail="Source file not found.")
        return FileResponse(
            DATA_DIRECTORY / source_file,
            media_type="text/csv",
            filename=source_file,
        )

    @app.get(
        "/api/data/quality",
        response_model=DataQualityReport,
        tags=["data"],
    )
    def get_data_quality() -> DataQualityReport:
        """Return completeness evidence for source fields used by the semantic layer."""
        return get_data_quality_report(DATA_DIRECTORY)

    @app.get(
        "/api/graph/relationships",
        response_model=RelationshipGraph,
        tags=["graph"],
    )
    def get_graph_relationships() -> RelationshipGraph:
        """Return the semantic relationship graph for visualization and traversal."""
        return get_relationship_graph(DATA_DIRECTORY)

    @app.get("/api/semantic/contracts", response_model=list[ContractSummary], tags=["semantic"])
    def get_contracts() -> list[ContractSummary]:
        """Return canonical vendor-contract records with source relationship coverage."""
        return get_contract_summaries(DATA_DIRECTORY)

    @app.get(
        "/api/semantic/financials/summary",
        response_model=list[FinancialScenarioTotal],
        tags=["semantic"],
    )
    def get_financial_summary() -> list[FinancialScenarioTotal]:
        """Return financial totals while retaining each source scenario separately."""
        return get_financial_scenario_totals(DATA_DIRECTORY)

    @app.get(
        "/api/semantic/operations/contracts",
        response_model=list[OperationalContractProfile],
        tags=["semantic"],
    )
    def get_operational_contracts() -> list[OperationalContractProfile]:
        """Return contract-level operational, SLA, and dependency risk information."""
        return get_operational_contract_profiles(DATA_DIRECTORY)

    @app.get(
        "/api/decisions/renewal-reviews",
        response_model=list[DecisionCandidate],
        tags=["decisions"],
    )
    def get_renewal_review_decisions() -> list[DecisionCandidate]:
        """Return governed draft renewal-review decisions with evidence."""
        return get_renewal_review_candidates(DATA_DIRECTORY)

    return app


app = create_app()