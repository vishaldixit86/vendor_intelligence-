---
title: Procurement Workbench Requirements Coverage
description: Source-backed coverage and limitations for the Vendor Intelligence demo
author: Procurement Intelligence Demo
ms.date: 2026-09-30
ms.topic: reference
keywords:
  - procurement
  - vendor intelligence
  - source coverage
---

## Source Inventory

| Source | Available evidence | Important limits |
| --- | --- | --- |
| `CT_Vendor_Technology_Forecast.csv` | Contract identifiers, dates, embedded synthetic SOW text, annual fee, SLA target and actual, breach, risk, owners, renewal fields | Snapshot and planning scenario; not an executed contract repository |
| `CT_Technology_Financials.csv` | Actual, Budget, Forecast scenarios, monthly values, YTD variance, currency, commercial parameters, categories | One recorded actual-through period; no invoices or transaction-level spend |
| `CT_Workforce_Organization.csv` | Assignments, FTE, role, location, applications, dependencies, failure impact, transition requirement | Workforce roster snapshot; no historical staffing changes or verified replacement capacity |

## Workflow Coverage

| Business question | Required sources | Available history | Deterministic reasoning | Evidence and UI | Status |
| --- | --- | --- | --- | --- | --- |
| How is a vendor performing? | Forecast, Financials, Workforce | SLA snapshot and monthly financials through recorded actual-through date | SLA target versus actual, risk, dependency, YTD variance | Contextual assistant and Vendor 360 review | Available |
| Is performance improving month over month? | Performance observations by month | No monthly SLA, incident, acceptance, or volume history | Not calculated | Assistant reports evidence gap | Not supported by supplied data |
| Is spend changing month over month? | Financials | Monthly 2026 scenario values | Aggregate monthly actual or budget values only | Comparison response evidence | Available for financials only |
| Compare vendors fairly | Financials and Forecast | Equivalent actual-through date where present | Require common currency and period; category-specific comparison requires the same service category | Comparison response includes eligibility and limits | Available with guardrails |
| Are contractual service levels met? | Forecast | Current recorded SLA period | Compare actual percentage with target; show breach flag | Comparison and negotiation evidence | Available as SLA proxy only |
| Are deliverables timely and accepted? | Contract, delivery, acceptance records | None | Not calculated | Assistant reports evidence gap | Not supported by supplied data |
| What should be negotiated? | Contract/SOW text, Financials, Workforce, Forecast | Current planning and actual-through snapshot | Propose non-binding asks from fee, variance, SLA, and dependency evidence | Negotiation specialist | Available with contract-validation guardrail |
| Consolidation or exit scenario | Financials, transition costs, dependencies, replacement capacity | Transition requirement only | Not calculated without transition cost and verified alternative capacity | Assistant must identify missing inputs | Not yet implemented |
| Human decision and approval | Draft recommendations and authorization policy | Draft review candidates | No automated approval or supplier action | Human Review panel | Available as draft review only |

## Semantic Rules

* Financial scenarios are always kept separate: Actual, Budget, and Forecast are never summed together.
* Calendar quarter totals sum the available monthly amounts. Q4 values are shown as zero only when the source monthly values are zero, not as an assumed completed quarter.
* SLA comparison uses the source target and actual for the recorded SLA period. It is not evidence of milestone delivery timeliness.
* Category-specific rankings require matching `Service_Category`, common currency, and equivalent `Actual_Through` period.
* When categories differ, the application permits only portfolio-level commercial comparison and warns against raw SLA rankings.
* Recommendations are proposed positions for human review. They do not create obligations, amend contracts, contact suppliers, or approve service credits.

## Architecture Status

The current working demo uses FastAPI, Pydantic, LangGraph, React, TypeScript, and the three CSV sources. PostgreSQL, pgvector, Neo4j, and object storage are not configured because no database or cloud credentials are supplied. They remain deployment integrations, not simulated live systems.

## Required Data for Expansion

* Versioned executed contracts and clause metadata
* Monthly SLA numerators and denominators, incidents, remediation, service volumes, and acceptance records
* Invoice and purchase-order detail with approved currency conversion policy
* Procurement policy and knowledge items with owner, version, approval, effective date, category, and access metadata
* Authorized external benchmarks with source, date, scope, and comparability definitions
* Transition cost, exit fee, retained cost, overlap, and verified replacement-capacity data for scenario simulation